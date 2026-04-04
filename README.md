# Mr. Sullivan

Multi-chain memecoin trading agent for Phantom Capital. Operates on Solana (primary), BSC, and Base via GMGN Agent API.

## Tech Stack
- Python 3.12
- GMGN Agent API integration
- Multi-chain wallet support

## Structure
- `main.py` — Entry point
- `src/` — Trading logic, chain adapters
- `config/` — Chain configs, strategy params

## Env Vars
See `.env.example`. Key vars:
- API keys for each chain
- Wallet credentials
- Risk parameters

## Run
```bash
pip install -r requirements.txt
python main.py
```

