import asyncio
from typing import List, Dict
from sqlalchemy import func, text
from src.services.gmgn_service import gmgn_service
from src.database import get_db_transaction
from src.models.signal import Signal, ActionTaken
from src.models.blacklist import Blacklist
from config.settings import settings
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

async def scan_for_signals():
    """Main discovery task - runs every 2 minutes"""
    try:
        logger.info("Starting signal discovery scan...")
        
        all_tokens = []
        
        # Get tokens from multiple sources
        for chain in settings.SUPPORTED_CHAINS:
            # 1. Trending tokens
            trending = await gmgn_service.get_trending_tokens(chain=chain, limit=50)
            all_tokens.extend([{**token, 'chain': chain, 'source': 'trending'} for token in trending])
            
            # 2. Migrated tokens from trenches
            migrated = await gmgn_service.get_trenches(stage="migrated", chain=chain)
            all_tokens.extend([{**token, 'chain': chain, 'source': 'trenches'} for token in migrated])
            
            await asyncio.sleep(0.1)  # Brief pause between chains
        
        # 3. Smart money convergence (cross-chain)
        convergence_tokens = await detect_smart_money_convergence()
        all_tokens.extend(convergence_tokens)
        
        # Deduplicate by token_address + chain
        seen = set()
        unique_tokens = []
        for token in all_tokens:
            key = f"{token['chain']}:{token.get('token_address', token.get('address', ''))}"
            if key not in seen:
                seen.add(key)
                unique_tokens.append(token)
        
        logger.info(f"Found {len(unique_tokens)} unique tokens to analyze")
        
        # Process each token
        processed_count = 0
        for token in unique_tokens:
            try:
                await process_token_signal(token)
                processed_count += 1
                await asyncio.sleep(0.05)  # Small delay to avoid overwhelming APIs
            except Exception as e:
                logger.error(f"Error processing token {token.get('token_address', 'unknown')}: {e}")
        
        logger.info(f"Signal discovery completed. Processed {processed_count}/{len(unique_tokens)} tokens")
        
    except Exception as e:
        logger.error(f"Signal discovery error: {e}")

async def detect_smart_money_convergence() -> List[Dict]:
    """Detect when multiple smart wallets buy the same token"""
    try:
        convergence_tokens = []
        
        for chain in settings.SUPPORTED_CHAINS:
            # This would need to be implemented based on GMGN's smart wallet activity endpoint
            # For now, returning empty list as the exact endpoint structure isn't specified
            pass
        
        return convergence_tokens
        
    except Exception as e:
        logger.error(f"Smart money convergence detection error: {e}")
        return []

async def process_token_signal(token_data: Dict):
    """Process a single token for signal generation"""
    try:
        token_address = token_data.get('token_address', token_data.get('address'))
        chain = token_data['chain']
        
        if not token_address:
            return
        
        # Check if token is blacklisted
        with get_db_transaction() as db:
            blacklisted = db.query(Blacklist).filter(
                Blacklist.token_address == token_address,
                Blacklist.chain == chain
            ).first()
            
            if blacklisted:
                logger.debug(f"Token {token_address} is blacklisted: {blacklisted.reason}")
                return
            
            # Check if we already have a recent signal for this token
            recent_signal = db.query(Signal).filter(
                Signal.token_address == token_address,
                Signal.chain == chain,
                Signal.created_at >= datetime.now(timezone.utc) - timedelta(hours=1)
            ).first()
            
            if recent_signal:
                logger.debug(f"Recent signal exists for {token_address}")
                return
        
        # Step 1: Security Gate (instant reject)
        if not await security_gate_check(token_address, chain):
            return
        
        # Step 2: Get detailed token information
        token_info = await gmgn_service.get_token_info(token_address, chain)
        pool_info = await gmgn_service.get_token_pool_info(token_address, chain)
        
        # Step 3: Score the token
        signal_score, score_breakdown = calculate_signal_score(token_info, pool_info)
        
        # Only proceed if score is above threshold
        if signal_score < settings.MIN_SIGNAL_SCORE:
            logger.debug(f"Token {token_address} score too low: {signal_score}")
            return
        
        # Create signal record
        with get_db_transaction() as db:
            signal = Signal(
                token_address=token_address,
                token_name=token_info.get('name'),
                chain=chain,
                signal_score=signal_score,
                holder_health_score=score_breakdown['holder_health'],
                liquidity_score=score_breakdown['liquidity'],
                momentum_score=score_breakdown['momentum'],
                smart_money_score=score_breakdown['smart_money'],
                creator_trust_score=score_breakdown['creator_trust'],
                action_taken=ActionTaken.QUEUED,
                smart_wallets_count=token_info.get('smart_wallets', 0),
                fresh_wallet_rate=token_info.get('fresh_wallet_rate', 0),
                top_10_holder_rate=token_info.get('top_10_holder_rate', 0),
                liquidity_usd=pool_info.get('liquidity', 0),
                volume_24h=token_info.get('volume_24h', 0)
            )
            
            db.add(signal)
            
        logger.info(f"New signal created: {token_address} (score: {signal_score})")
        
    except Exception as e:
        logger.error(f"Error processing token signal: {e}")

async def security_gate_check(token_address: str, chain: str) -> bool:
    """Security gate - hard reject criteria"""
    try:
        security_data = await gmgn_service.get_token_security(token_address, chain)
        
        # Hard reject conditions
        if security_data.get('is_honeypot'):
            await add_to_blacklist(token_address, chain, "honeypot_detected")
            return False
            
        if not security_data.get('can_sell', True):
            await add_to_blacklist(token_address, chain, "cannot_sell")
            return False
            
        if security_data.get('is_blacklist') and not security_data.get('is_renounced'):
            await add_to_blacklist(token_address, chain, "blacklisted_not_renounced")
            return False
            
        buy_tax = security_data.get('buy_tax', 0)
        sell_tax = security_data.get('sell_tax', 0)
        if buy_tax > 5 or sell_tax > 5:
            await add_to_blacklist(token_address, chain, f"high_tax_buy_{buy_tax}_sell_{sell_tax}")
            return False
            
        if chain in ['bsc', 'base'] and not security_data.get('is_open_source'):
            await add_to_blacklist(token_address, chain, "not_open_source")
            return False
            
        # Liquidity lock check
        lock_info = security_data.get('lock_summary', {})
        if not lock_info.get('is_locked') or lock_info.get('lock_percent', 0) < 80:
            await add_to_blacklist(token_address, chain, "insufficient_liquidity_lock")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Security gate error for {token_address}: {e}")
        return False

async def add_to_blacklist(token_address: str, chain: str, reason: str):
    """Add token to blacklist"""
    try:
        with get_db_transaction() as db:
            # Check if already blacklisted
            existing = db.query(Blacklist).filter(
                Blacklist.token_address == token_address,
                Blacklist.chain == chain
            ).first()
            
            if not existing:
                blacklist_entry = Blacklist(
                    token_address=token_address,
                    chain=chain,
                    reason=reason,
                    blacklisted_at=datetime.utcnow()
                )
                db.add(blacklist_entry)
                logger.info(f"Added {token_address} to blacklist: {reason}")
                
    except Exception as e:
        logger.error(f"Error adding to blacklist: {e}")

def calculate_signal_score(token_info: Dict, pool_info: Dict) -> tuple[int, Dict]:
    """Calculate signal score based on GMGN data"""
    scores = {
        'holder_health': 0,
        'liquidity': 0, 
        'momentum': 0,
        'smart_money': 0,
        'creator_trust': 0
    }
    
    # Holder Health (25 points max)
    top_10_rate = token_info.get('top_10_holder_rate', 100)
    if top_10_rate < 30:
        scores['holder_health'] += 10
    elif top_10_rate < 50:
        scores['holder_health'] += 5
        
    fresh_wallet_rate = token_info.get('fresh_wallet_rate', 100)
    if fresh_wallet_rate < 20:
        scores['holder_health'] += 5
    elif fresh_wallet_rate > 40:
        scores['holder_health'] += 0
        
    if token_info.get('bluechip_owner_percentage', 0) > 5:
        scores['holder_health'] += 5
        
    if token_info.get('rat_trader_percentage', 100) < 10:
        scores['holder_health'] += 3
        
    if token_info.get('bundler_percentage', 100) < 5:
        scores['holder_health'] += 2
    
    # Liquidity Quality (20 points max)
    liquidity = pool_info.get('liquidity', 0)
    if liquidity > 100000:
        scores['liquidity'] += 10
    elif liquidity > 50000:
        scores['liquidity'] += 7
    elif liquidity > 10000:
        scores['liquidity'] += 4
    else:
        return 0, scores  # Reject if liquidity too low
        
    initial_liquidity = pool_info.get('initial_liquidity', liquidity)
    if liquidity / max(initial_liquidity, 1) > 1.5:
        scores['liquidity'] += 5
    
    volume_to_liquidity = token_info.get('volume_24h', 0) / max(liquidity, 1)
    if volume_to_liquidity > 0.5:
        scores['liquidity'] += 3
    elif volume_to_liquidity > 0.2:
        scores['liquidity'] += 2
    
    # Momentum (20 points max)
    price_change_1h = token_info.get('price_change_1h', 0)
    if price_change_1h > 20:
        scores['momentum'] += 8
    elif price_change_1h > 10:
        scores['momentum'] += 5
    elif price_change_1h > 0:
        scores['momentum'] += 2
    
    volume_24h = token_info.get('volume_24h', 0)
    if volume_24h > 500000:
        scores['momentum'] += 6
    elif volume_24h > 100000:
        scores['momentum'] += 4
    elif volume_24h > 50000:
        scores['momentum'] += 2
    
    txns_1h = token_info.get('txns_1h', 0)
    if txns_1h > 100:
        scores['momentum'] += 4
    elif txns_1h > 50:
        scores['momentum'] += 2
    
    volume_change_24h = token_info.get('volume_change_24h', 0)
    if volume_change_24h > 100:
        scores['momentum'] += 2
    
    # Smart Money (20 points max)
    smart_wallets = token_info.get('smart_wallets', 0)
    if smart_wallets > 10:
        scores['smart_money'] += 8
    elif smart_wallets > 5:
        scores['smart_money'] += 5
    elif smart_wallets > 2:
        scores['smart_money'] += 3
    
    smart_degen_call = token_info.get('smart_degen_call', False)
    if smart_degen_call:
        scores['smart_money'] += 4
    
    kol_call = token_info.get('kol_call', False)
    if kol_call:
        scores['smart_money'] += 3
    
    insider_percentage = token_info.get('insider_percentage', 100)
    if insider_percentage < 5:
        scores['smart_money'] += 3
    elif insider_percentage < 15:
        scores['smart_money'] += 1
    
    bluechip_owners = token_info.get('bluechip_owner_percentage', 0)
    if bluechip_owners > 10:
        scores['smart_money'] += 2
    
    # Creator Trust (15 points max)
    creator_twitter_followers = token_info.get('creator_twitter_followers', 0)
    if creator_twitter_followers > 10000:
        scores['creator_trust'] += 5
    elif creator_twitter_followers > 1000:
        scores['creator_trust'] += 3
    elif creator_twitter_followers > 100:
        scores['creator_trust'] += 1
    
    if token_info.get('creator_close_token', True):
        scores['creator_trust'] += 0  # Neutral if creator can close
    else:
        scores['creator_trust'] += 3  # Bonus if creator renounced
    
    dev_bought = token_info.get('dev_bought', False)
    if not dev_bought:
        scores['creator_trust'] += 2
    
    is_show_off = token_info.get('is_show_off', False)
    if not is_show_off:
        scores['creator_trust'] += 2
    
    token_age_hours = token_info.get('age_hours', 0)
    if token_age_hours > 24:
        scores['creator_trust'] += 2
    elif token_age_hours > 6:
        scores['creator_trust'] += 1
    
    website_twitter = token_info.get('website', '') or token_info.get('twitter', '')
    if website_twitter:
        scores['creator_trust'] += 1
    
    # Calculate total score
    total_score = sum(scores.values())
    
    return total_score, scores
