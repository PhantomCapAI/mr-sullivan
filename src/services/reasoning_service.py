import anthropic
from typing import Dict, Optional
from config.settings import settings
from src.redis_client import redis_client
import json
import logging
import time

logger = logging.getLogger(__name__)

class ReasoningService:
    def __init__(self):
        self.client = None
        self._available = False
        self.model = "claude-3-sonnet-20240229"
        self.max_calls_per_hour = settings.MAX_CLAUDE_CALLS_PER_HOUR
        self.cache_ttl = settings.CLAUDE_CACHE_TTL_SECONDS

        if settings.ANTHROPIC_API_KEY:
            try:
                self.client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
                self._available = True
                logger.info("Anthropic client initialized")
            except Exception as e:
                logger.warning(f"Anthropic unavailable: {e}")
        else:
            logger.warning("ANTHROPIC_API_KEY not set. Claude reasoning disabled.")
    
    async def _check_rate_limit(self) -> bool:
        """Check if we can make another Claude API call"""
        current_hour = int(time.time() // 3600)
        rate_limit_key = f"claude_calls:{current_hour}"
        
        current_calls = await redis_client.get(rate_limit_key) or 0
        if current_calls >= self.max_calls_per_hour:
            logger.warning(f"Claude API rate limit exceeded: {current_calls}/{self.max_calls_per_hour}")
            return False
        
        return True
    
    async def _increment_rate_limit(self):
        """Increment the rate limit counter"""
        current_hour = int(time.time() // 3600)
        rate_limit_key = f"claude_calls:{current_hour}"
        await redis_client.increment(rate_limit_key, ttl=3600)
    
    async def analyze_signal(self, signal_data: Dict) -> Optional[Dict]:
        """Analyze a trading signal using Claude"""
        if not self._available:
            logger.debug("Claude analysis skipped (not configured)")
            return None

        # Check cache first
        cache_key = f"claude_analysis:{signal_data['token_address']}:{signal_data['chain']}"
        cached_result = await redis_client.get(cache_key)
        if cached_result:
            logger.info(f"Using cached Claude analysis for {signal_data['token_address']}")
            return cached_result
        
        # Check rate limit
        if not await self._check_rate_limit():
            logger.warning("Claude API rate limit exceeded, skipping analysis")
            return None
        
        try:
            prompt = self._create_analysis_prompt(signal_data)
            
            message = await self.client.messages.create(
                model=self.model,
                max_tokens=500,
                temperature=0.1,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            await self._increment_rate_limit()
            
            # Parse Claude's response
            response_text = message.content[0].text
            analysis = self._parse_response(response_text)
            
            # Cache the result
            await redis_client.set(cache_key, analysis, ttl=self.cache_ttl)
            
            logger.info(f"Claude analysis completed for {signal_data['token_address']}: {analysis['action']}")
            return analysis
            
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return None
    
    def _create_analysis_prompt(self, signal_data: Dict) -> str:
        """Create a structured prompt for Claude"""
        return f"""You are Sullivan, a memecoin trading analyst. Analyze this token for potential trade:

TOKEN DATA:
- Address: {signal_data['token_address']}
- Name: {signal_data.get('token_name', 'Unknown')}
- Chain: {signal_data['chain']}
- Signal Score: {signal_data['signal_score']}/100

SCORING BREAKDOWN:
- Holder Health: {signal_data.get('holder_health_score', 0)}/25
- Liquidity Quality: {signal_data.get('liquidity_score', 0)}/20
- Momentum: {signal_data.get('momentum_score', 0)}/20
- Smart Money: {signal_data.get('smart_money_score', 0)}/20
- Creator Trust: {signal_data.get('creator_trust_score', 0)}/15

KEY METRICS:
- Smart Wallets Count: {signal_data.get('smart_wallets_count', 0)}
- Fresh Wallet Rate: {signal_data.get('fresh_wallet_rate', 0):.2%}
- Top 10 Holder Rate: {signal_data.get('top_10_holder_rate', 0):.2%}
- Liquidity: ${signal_data.get('liquidity_usd', 0):,.2f}
- 24h Volume: ${signal_data.get('volume_24h', 0):,.2f}

Provide your decision in this exact format:
ACTION: [BUY/WATCH/SKIP]
CONFIDENCE: [0-100]
REASON: [Brief explanation of your decision]

Consider:
1. Is this organic growth or manufactured?
2. Is the risk/reward favorable given the metrics?
3. What could go wrong with this trade?
4. Does the smart money activity suggest genuine interest?
"""
    
    def _parse_response(self, response_text: str) -> Dict:
        """Parse Claude's structured response"""
        try:
            lines = response_text.strip().split('\n')
            action = "SKIP"
            confidence = 0
            reason = "Unable to parse response"
            
            for line in lines:
                line = line.strip()
                if line.startswith("ACTION:"):
                    action = line.split(":", 1)[1].strip()
                elif line.startswith("CONFIDENCE:"):
                    try:
                        confidence = int(line.split(":", 1)[1].strip())
                    except ValueError:
                        confidence = 0
                elif line.startswith("REASON:"):
                    reason = line.split(":", 1)[1].strip()
            
            return {
                "action": action,
                "confidence": confidence,
                "reasoning": reason,
                "raw_response": response_text
            }
            
        except Exception as e:
            logger.error(f"Error parsing Claude response: {e}")
            return {
                "action": "SKIP",
                "confidence": 0,
                "reasoning": f"Error parsing response: {str(e)}",
                "raw_response": response_text
            }

reasoning_service = ReasoningService()
