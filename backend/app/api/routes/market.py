"""
Market data routes — OHLCV candles + symbol search.
No authentication required (public endpoints).
"""
from fastapi import APIRouter, Query
from app.data.market_data import fetch_market_data
import asyncio, random
from datetime import datetime, timedelta
import httpx

router = APIRouter(prefix="/api/v1/market", tags=["market"])

# ── Symbol catalogue ──────────────────────────────────────────────────────────
# Each entry has: symbol (display/TV-style), yf (Yahoo Finance ticker),
# name, exchange, cat (sub-category). The yf field is used for data fetching;
# symbol is what users see and what gets sent to the signal endpoint.
SYMBOLS = {
    "stocks_us": [
        # Mega Cap Tech
        {"symbol":"AAPL",  "yf":"AAPL",  "name":"Apple Inc.",           "exchange":"NASDAQ","cat":"US Tech"},
        {"symbol":"MSFT",  "yf":"MSFT",  "name":"Microsoft Corp.",       "exchange":"NASDAQ","cat":"US Tech"},
        {"symbol":"NVDA",  "yf":"NVDA",  "name":"NVIDIA Corp.",          "exchange":"NASDAQ","cat":"US Tech"},
        {"symbol":"GOOGL", "yf":"GOOGL", "name":"Alphabet Inc.",         "exchange":"NASDAQ","cat":"US Tech"},
        {"symbol":"AMZN",  "yf":"AMZN",  "name":"Amazon.com Inc.",       "exchange":"NASDAQ","cat":"US Tech"},
        {"symbol":"META",  "yf":"META",  "name":"Meta Platforms",        "exchange":"NASDAQ","cat":"US Tech"},
        {"symbol":"TSLA",  "yf":"TSLA",  "name":"Tesla Inc.",            "exchange":"NASDAQ","cat":"US Tech"},
        {"symbol":"AVGO",  "yf":"AVGO",  "name":"Broadcom Inc.",         "exchange":"NASDAQ","cat":"US Tech"},
        {"symbol":"AMD",   "yf":"AMD",   "name":"AMD",                   "exchange":"NASDAQ","cat":"US Tech"},
        {"symbol":"INTC",  "yf":"INTC",  "name":"Intel Corp.",           "exchange":"NASDAQ","cat":"US Tech"},
        {"symbol":"QCOM",  "yf":"QCOM",  "name":"Qualcomm Inc.",         "exchange":"NASDAQ","cat":"US Tech"},
        {"symbol":"TXN",   "yf":"TXN",   "name":"Texas Instruments",     "exchange":"NASDAQ","cat":"US Tech"},
        {"symbol":"MU",    "yf":"MU",    "name":"Micron Technology",     "exchange":"NASDAQ","cat":"US Tech"},
        {"symbol":"ARM",   "yf":"ARM",   "name":"ARM Holdings",          "exchange":"NASDAQ","cat":"US Tech"},
        {"symbol":"SMCI",  "yf":"SMCI",  "name":"Super Micro Computer",  "exchange":"NASDAQ","cat":"US Tech"},
        # Software & Cloud
        {"symbol":"ORCL",  "yf":"ORCL",  "name":"Oracle Corp.",          "exchange":"NYSE",  "cat":"US Software"},
        {"symbol":"CRM",   "yf":"CRM",   "name":"Salesforce Inc.",       "exchange":"NYSE",  "cat":"US Software"},
        {"symbol":"ADBE",  "yf":"ADBE",  "name":"Adobe Inc.",            "exchange":"NASDAQ","cat":"US Software"},
        {"symbol":"NOW",   "yf":"NOW",   "name":"ServiceNow Inc.",       "exchange":"NYSE",  "cat":"US Software"},
        {"symbol":"SNOW",  "yf":"SNOW",  "name":"Snowflake Inc.",        "exchange":"NYSE",  "cat":"US Software"},
        {"symbol":"DDOG",  "yf":"DDOG",  "name":"Datadog Inc.",          "exchange":"NASDAQ","cat":"US Software"},
        {"symbol":"CRWD",  "yf":"CRWD",  "name":"CrowdStrike Holdings",  "exchange":"NASDAQ","cat":"US Software"},
        {"symbol":"PANW",  "yf":"PANW",  "name":"Palo Alto Networks",    "exchange":"NASDAQ","cat":"US Software"},
        {"symbol":"NET",   "yf":"NET",   "name":"Cloudflare Inc.",       "exchange":"NYSE",  "cat":"US Software"},
        {"symbol":"PLTR",  "yf":"PLTR",  "name":"Palantir Technologies", "exchange":"NYSE",  "cat":"US Software"},
        {"symbol":"COIN",  "yf":"COIN",  "name":"Coinbase Global",       "exchange":"NASDAQ","cat":"US Software"},
        {"symbol":"MSTR",  "yf":"MSTR",  "name":"MicroStrategy Inc.",    "exchange":"NASDAQ","cat":"US Software"},
        # Financials
        {"symbol":"JPM",   "yf":"JPM",   "name":"JPMorgan Chase",        "exchange":"NYSE",  "cat":"US Finance"},
        {"symbol":"GS",    "yf":"GS",    "name":"Goldman Sachs",         "exchange":"NYSE",  "cat":"US Finance"},
        {"symbol":"MS",    "yf":"MS",    "name":"Morgan Stanley",        "exchange":"NYSE",  "cat":"US Finance"},
        {"symbol":"BAC",   "yf":"BAC",   "name":"Bank of America",       "exchange":"NYSE",  "cat":"US Finance"},
        {"symbol":"WFC",   "yf":"WFC",   "name":"Wells Fargo",           "exchange":"NYSE",  "cat":"US Finance"},
        {"symbol":"C",     "yf":"C",     "name":"Citigroup Inc.",        "exchange":"NYSE",  "cat":"US Finance"},
        {"symbol":"BLK",   "yf":"BLK",   "name":"BlackRock Inc.",        "exchange":"NYSE",  "cat":"US Finance"},
        {"symbol":"SCHW",  "yf":"SCHW",  "name":"Charles Schwab",        "exchange":"NYSE",  "cat":"US Finance"},
        {"symbol":"AXP",   "yf":"AXP",   "name":"American Express",      "exchange":"NYSE",  "cat":"US Finance"},
        {"symbol":"V",     "yf":"V",     "name":"Visa Inc.",             "exchange":"NYSE",  "cat":"US Finance"},
        {"symbol":"MA",    "yf":"MA",    "name":"Mastercard Inc.",       "exchange":"NYSE",  "cat":"US Finance"},
        {"symbol":"PYPL",  "yf":"PYPL",  "name":"PayPal Holdings",       "exchange":"NASDAQ","cat":"US Finance"},
        {"symbol":"HOOD",  "yf":"HOOD",  "name":"Robinhood Markets",     "exchange":"NASDAQ","cat":"US Finance"},
        {"symbol":"SQ",    "yf":"SQ",    "name":"Block Inc.",            "exchange":"NYSE",  "cat":"US Finance"},
        # Healthcare
        {"symbol":"JNJ",   "yf":"JNJ",   "name":"Johnson & Johnson",     "exchange":"NYSE",  "cat":"US Healthcare"},
        {"symbol":"UNH",   "yf":"UNH",   "name":"UnitedHealth Group",    "exchange":"NYSE",  "cat":"US Healthcare"},
        {"symbol":"LLY",   "yf":"LLY",   "name":"Eli Lilly",            "exchange":"NYSE",  "cat":"US Healthcare"},
        {"symbol":"ABBV",  "yf":"ABBV",  "name":"AbbVie Inc.",           "exchange":"NYSE",  "cat":"US Healthcare"},
        {"symbol":"MRK",   "yf":"MRK",   "name":"Merck & Co.",          "exchange":"NYSE",  "cat":"US Healthcare"},
        {"symbol":"PFE",   "yf":"PFE",   "name":"Pfizer Inc.",           "exchange":"NYSE",  "cat":"US Healthcare"},
        {"symbol":"TMO",   "yf":"TMO",   "name":"Thermo Fisher Scientific","exchange":"NYSE","cat":"US Healthcare"},
        {"symbol":"ABT",   "yf":"ABT",   "name":"Abbott Laboratories",   "exchange":"NYSE",  "cat":"US Healthcare"},
        {"symbol":"AMGN",  "yf":"AMGN",  "name":"Amgen Inc.",            "exchange":"NASDAQ","cat":"US Healthcare"},
        {"symbol":"GILD",  "yf":"GILD",  "name":"Gilead Sciences",       "exchange":"NASDAQ","cat":"US Healthcare"},
        # Consumer
        {"symbol":"WMT",   "yf":"WMT",   "name":"Walmart Inc.",          "exchange":"NYSE",  "cat":"US Consumer"},
        {"symbol":"COST",  "yf":"COST",  "name":"Costco Wholesale",      "exchange":"NASDAQ","cat":"US Consumer"},
        {"symbol":"TGT",   "yf":"TGT",   "name":"Target Corp.",          "exchange":"NYSE",  "cat":"US Consumer"},
        {"symbol":"MCD",   "yf":"MCD",   "name":"McDonald's Corp.",      "exchange":"NYSE",  "cat":"US Consumer"},
        {"symbol":"SBUX",  "yf":"SBUX",  "name":"Starbucks Corp.",       "exchange":"NASDAQ","cat":"US Consumer"},
        {"symbol":"NKE",   "yf":"NKE",   "name":"Nike Inc.",             "exchange":"NYSE",  "cat":"US Consumer"},
        {"symbol":"HD",    "yf":"HD",    "name":"Home Depot",            "exchange":"NYSE",  "cat":"US Consumer"},
        {"symbol":"PG",    "yf":"PG",    "name":"Procter & Gamble",      "exchange":"NYSE",  "cat":"US Consumer"},
        {"symbol":"KO",    "yf":"KO",    "name":"Coca-Cola Co.",         "exchange":"NYSE",  "cat":"US Consumer"},
        {"symbol":"PEP",   "yf":"PEP",   "name":"PepsiCo Inc.",          "exchange":"NASDAQ","cat":"US Consumer"},
        # Energy
        {"symbol":"XOM",   "yf":"XOM",   "name":"Exxon Mobil",           "exchange":"NYSE",  "cat":"US Energy"},
        {"symbol":"CVX",   "yf":"CVX",   "name":"Chevron Corp.",         "exchange":"NYSE",  "cat":"US Energy"},
        {"symbol":"SLB",   "yf":"SLB",   "name":"SLB (Schlumberger)",    "exchange":"NYSE",  "cat":"US Energy"},
        {"symbol":"EOG",   "yf":"EOG",   "name":"EOG Resources",         "exchange":"NYSE",  "cat":"US Energy"},
        {"symbol":"COP",   "yf":"COP",   "name":"ConocoPhillips",        "exchange":"NYSE",  "cat":"US Energy"},
        # Industrials
        {"symbol":"BA",    "yf":"BA",    "name":"Boeing Co.",            "exchange":"NYSE",  "cat":"US Industrial"},
        {"symbol":"CAT",   "yf":"CAT",   "name":"Caterpillar Inc.",      "exchange":"NYSE",  "cat":"US Industrial"},
        {"symbol":"GE",    "yf":"GE",    "name":"GE Aerospace",          "exchange":"NYSE",  "cat":"US Industrial"},
        {"symbol":"LMT",   "yf":"LMT",   "name":"Lockheed Martin",       "exchange":"NYSE",  "cat":"US Industrial"},
        {"symbol":"RTX",   "yf":"RTX",   "name":"RTX Corp.",             "exchange":"NYSE",  "cat":"US Industrial"},
        {"symbol":"HON",   "yf":"HON",   "name":"Honeywell Intl.",       "exchange":"NASDAQ","cat":"US Industrial"},
        # EV / Autos
        {"symbol":"RIVN",  "yf":"RIVN",  "name":"Rivian Automotive",     "exchange":"NASDAQ","cat":"EV & Autos"},
        {"symbol":"NIO",   "yf":"NIO",   "name":"NIO Inc.",              "exchange":"NYSE",  "cat":"EV & Autos"},
        {"symbol":"LI",    "yf":"LI",    "name":"Li Auto",               "exchange":"NASDAQ","cat":"EV & Autos"},
        {"symbol":"XPEV",  "yf":"XPEV",  "name":"XPeng Inc.",            "exchange":"NYSE",  "cat":"EV & Autos"},
        # China ADRs
        {"symbol":"BABA",  "yf":"BABA",  "name":"Alibaba Group",         "exchange":"NYSE",  "cat":"China ADR"},
        {"symbol":"JD",    "yf":"JD",    "name":"JD.com Inc.",           "exchange":"NASDAQ","cat":"China ADR"},
        {"symbol":"PDD",   "yf":"PDD",   "name":"PDD Holdings",          "exchange":"NASDAQ","cat":"China ADR"},
        {"symbol":"BIDU",  "yf":"BIDU",  "name":"Baidu Inc.",            "exchange":"NASDAQ","cat":"China ADR"},
    ],
    "stocks_eu": [
        # UK (LSE)
        {"symbol":"AZN.L", "yf":"AZN.L", "name":"AstraZeneca",          "exchange":"LSE","cat":"UK"},
        {"symbol":"HSBA.L","yf":"HSBA.L","name":"HSBC Holdings",         "exchange":"LSE","cat":"UK"},
        {"symbol":"BP.L",  "yf":"BP.L",  "name":"BP plc",               "exchange":"LSE","cat":"UK"},
        {"symbol":"SHEL.L","yf":"SHEL.L","name":"Shell plc",             "exchange":"LSE","cat":"UK"},
        {"symbol":"RIO.L", "yf":"RIO.L", "name":"Rio Tinto",            "exchange":"LSE","cat":"UK"},
        {"symbol":"GSK.L", "yf":"GSK.L", "name":"GSK plc",              "exchange":"LSE","cat":"UK"},
        {"symbol":"ULVR.L","yf":"ULVR.L","name":"Unilever",             "exchange":"LSE","cat":"UK"},
        {"symbol":"LLOY.L","yf":"LLOY.L","name":"Lloyds Banking Group",  "exchange":"LSE","cat":"UK"},
        {"symbol":"BARC.L","yf":"BARC.L","name":"Barclays plc",          "exchange":"LSE","cat":"UK"},
        {"symbol":"VOD.L", "yf":"VOD.L", "name":"Vodafone Group",        "exchange":"LSE","cat":"UK"},
        {"symbol":"DGE.L", "yf":"DGE.L", "name":"Diageo plc",           "exchange":"LSE","cat":"UK"},
        {"symbol":"BHP.L", "yf":"BHP.L", "name":"BHP Group",            "exchange":"LSE","cat":"UK"},
        # Germany (XETRA)
        {"symbol":"SAP.DE","yf":"SAP.DE","name":"SAP SE",               "exchange":"XETRA","cat":"Germany"},
        {"symbol":"SIE.DE","yf":"SIE.DE","name":"Siemens AG",           "exchange":"XETRA","cat":"Germany"},
        {"symbol":"ALV.DE","yf":"ALV.DE","name":"Allianz SE",           "exchange":"XETRA","cat":"Germany"},
        {"symbol":"BMW.DE","yf":"BMW.DE","name":"BMW AG",               "exchange":"XETRA","cat":"Germany"},
        {"symbol":"VOW3.DE","yf":"VOW3.DE","name":"Volkswagen AG",      "exchange":"XETRA","cat":"Germany"},
        {"symbol":"MBG.DE","yf":"MBG.DE","name":"Mercedes-Benz Group",  "exchange":"XETRA","cat":"Germany"},
        {"symbol":"BAYN.DE","yf":"BAYN.DE","name":"Bayer AG",           "exchange":"XETRA","cat":"Germany"},
        {"symbol":"ADS.DE","yf":"ADS.DE","name":"adidas AG",            "exchange":"XETRA","cat":"Germany"},
        # France (Euronext Paris)
        {"symbol":"MC.PA", "yf":"MC.PA", "name":"LVMH Moët Hennessy",  "exchange":"EPA","cat":"France"},
        {"symbol":"AIR.PA","yf":"AIR.PA","name":"Airbus SE",            "exchange":"EPA","cat":"France"},
        {"symbol":"TTE.PA","yf":"TTE.PA","name":"TotalEnergies SE",     "exchange":"EPA","cat":"France"},
        {"symbol":"OR.PA", "yf":"OR.PA", "name":"L'Oréal S.A.",         "exchange":"EPA","cat":"France"},
        {"symbol":"BNP.PA","yf":"BNP.PA","name":"BNP Paribas",          "exchange":"EPA","cat":"France"},
        # Netherlands
        {"symbol":"ASML.AS","yf":"ASML.AS","name":"ASML Holding",       "exchange":"AMS","cat":"Netherlands"},
        {"symbol":"INGA.AS","yf":"INGA.AS","name":"ING Group",          "exchange":"AMS","cat":"Netherlands"},
        # Switzerland
        {"symbol":"NESN.SW","yf":"NESN.SW","name":"Nestlé S.A.",        "exchange":"SWX","cat":"Switzerland"},
        {"symbol":"NOVN.SW","yf":"NOVN.SW","name":"Novartis AG",        "exchange":"SWX","cat":"Switzerland"},
        {"symbol":"ROG.SW", "yf":"ROG.SW", "name":"Roche Holding",      "exchange":"SWX","cat":"Switzerland"},
    ],
    "stocks_asia": [
        {"symbol":"7203.T","yf":"7203.T","name":"Toyota Motor",          "exchange":"TSE","cat":"Japan"},
        {"symbol":"9984.T","yf":"9984.T","name":"SoftBank Group",        "exchange":"TSE","cat":"Japan"},
        {"symbol":"6758.T","yf":"6758.T","name":"Sony Group",            "exchange":"TSE","cat":"Japan"},
        {"symbol":"9432.T","yf":"9432.T","name":"NTT Corp.",             "exchange":"TSE","cat":"Japan"},
        {"symbol":"6861.T","yf":"6861.T","name":"Keyence Corp.",         "exchange":"TSE","cat":"Japan"},
        {"symbol":"7974.T","yf":"7974.T","name":"Nintendo Co.",          "exchange":"TSE","cat":"Japan"},
        {"symbol":"9983.T","yf":"9983.T","name":"Fast Retailing (UNIQLO)","exchange":"TSE","cat":"Japan"},
    ],
    "etfs": [
        # US Broad Market
        {"symbol":"SPY",  "yf":"SPY",  "name":"SPDR S&P 500 ETF",        "exchange":"NYSE","cat":"Broad Market"},
        {"symbol":"QQQ",  "yf":"QQQ",  "name":"Invesco Nasdaq 100 ETF",  "exchange":"NASDAQ","cat":"Broad Market"},
        {"symbol":"DIA",  "yf":"DIA",  "name":"SPDR Dow Jones ETF",      "exchange":"NYSE","cat":"Broad Market"},
        {"symbol":"IWM",  "yf":"IWM",  "name":"iShares Russell 2000",    "exchange":"NYSE","cat":"Broad Market"},
        {"symbol":"VTI",  "yf":"VTI",  "name":"Vanguard Total Stock",    "exchange":"NYSE","cat":"Broad Market"},
        {"symbol":"VOO",  "yf":"VOO",  "name":"Vanguard S&P 500",        "exchange":"NYSE","cat":"Broad Market"},
        # International
        {"symbol":"EFA",  "yf":"EFA",  "name":"iShares MSCI EAFE",       "exchange":"NYSE","cat":"International"},
        {"symbol":"VEA",  "yf":"VEA",  "name":"Vanguard FTSE Dev. Markets","exchange":"NYSE","cat":"International"},
        {"symbol":"EEM",  "yf":"EEM",  "name":"iShares MSCI Emerging",   "exchange":"NYSE","cat":"International"},
        {"symbol":"VWO",  "yf":"VWO",  "name":"Vanguard FTSE Emerging",  "exchange":"NYSE","cat":"International"},
        {"symbol":"VGK",  "yf":"VGK",  "name":"Vanguard FTSE Europe",    "exchange":"NYSE","cat":"International"},
        {"symbol":"EWJ",  "yf":"EWJ",  "name":"iShares MSCI Japan",      "exchange":"NYSE","cat":"International"},
        {"symbol":"EWZ",  "yf":"EWZ",  "name":"iShares MSCI Brazil",     "exchange":"NYSE","cat":"International"},
        {"symbol":"FXI",  "yf":"FXI",  "name":"iShares China Large-Cap", "exchange":"NYSE","cat":"International"},
        {"symbol":"EWY",  "yf":"EWY",  "name":"iShares MSCI South Korea","exchange":"NYSE","cat":"International"},
        # Fixed Income
        {"symbol":"TLT",  "yf":"TLT",  "name":"iShares 20+ Year Treasury","exchange":"NASDAQ","cat":"Bonds"},
        {"symbol":"IEF",  "yf":"IEF",  "name":"iShares 7-10 Year Treasury","exchange":"NASDAQ","cat":"Bonds"},
        {"symbol":"SHY",  "yf":"SHY",  "name":"iShares 1-3 Year Treasury","exchange":"NASDAQ","cat":"Bonds"},
        {"symbol":"AGG",  "yf":"AGG",  "name":"iShares Core U.S. Agg Bond","exchange":"NYSE","cat":"Bonds"},
        {"symbol":"BND",  "yf":"BND",  "name":"Vanguard Total Bond Market","exchange":"NASDAQ","cat":"Bonds"},
        {"symbol":"HYG",  "yf":"HYG",  "name":"iShares High Yield Corp","exchange":"NYSE","cat":"Bonds"},
        {"symbol":"LQD",  "yf":"LQD",  "name":"iShares IG Corp Bond",    "exchange":"NYSE","cat":"Bonds"},
        {"symbol":"EMB",  "yf":"EMB",  "name":"iShares JP Morgan EM Bond","exchange":"NYSE","cat":"Bonds"},
        {"symbol":"TIPS", "yf":"TIPS", "name":"iShares TIPS Bond",       "exchange":"NYSE","cat":"Bonds"},
        # Sector
        {"symbol":"XLK",  "yf":"XLK",  "name":"Technology Select Sector","exchange":"NYSE","cat":"Sectors"},
        {"symbol":"XLE",  "yf":"XLE",  "name":"Energy Select Sector",    "exchange":"NYSE","cat":"Sectors"},
        {"symbol":"XLF",  "yf":"XLF",  "name":"Financial Select Sector", "exchange":"NYSE","cat":"Sectors"},
        {"symbol":"XLV",  "yf":"XLV",  "name":"Health Care Select Sector","exchange":"NYSE","cat":"Sectors"},
        {"symbol":"XLI",  "yf":"XLI",  "name":"Industrial Select Sector","exchange":"NYSE","cat":"Sectors"},
        {"symbol":"XLY",  "yf":"XLY",  "name":"Consumer Discret. Sector","exchange":"NYSE","cat":"Sectors"},
        {"symbol":"XLP",  "yf":"XLP",  "name":"Consumer Staples Sector", "exchange":"NYSE","cat":"Sectors"},
        {"symbol":"XLU",  "yf":"XLU",  "name":"Utilities Select Sector", "exchange":"NYSE","cat":"Sectors"},
        {"symbol":"XLB",  "yf":"XLB",  "name":"Materials Select Sector", "exchange":"NYSE","cat":"Sectors"},
        {"symbol":"XLRE", "yf":"XLRE", "name":"Real Estate Select Sector","exchange":"NYSE","cat":"Sectors"},
        # Commodities ETF
        {"symbol":"GLD",  "yf":"GLD",  "name":"SPDR Gold Shares",        "exchange":"NYSE","cat":"Commodity ETF"},
        {"symbol":"IAU",  "yf":"IAU",  "name":"iShares Gold Trust",      "exchange":"NYSE","cat":"Commodity ETF"},
        {"symbol":"SLV",  "yf":"SLV",  "name":"iShares Silver Trust",    "exchange":"NYSE","cat":"Commodity ETF"},
        {"symbol":"GDX",  "yf":"GDX",  "name":"VanEck Gold Miners",      "exchange":"NYSE","cat":"Commodity ETF"},
        {"symbol":"GDXJ", "yf":"GDXJ", "name":"VanEck Junior Gold Miners","exchange":"NYSE","cat":"Commodity ETF"},
        {"symbol":"USO",  "yf":"USO",  "name":"United States Oil Fund",  "exchange":"NYSE","cat":"Commodity ETF"},
        {"symbol":"UNG",  "yf":"UNG",  "name":"United States Nat Gas",   "exchange":"NYSE","cat":"Commodity ETF"},
        # Thematic
        {"symbol":"ARKK", "yf":"ARKK", "name":"ARK Innovation ETF",      "exchange":"NYSE","cat":"Thematic"},
        {"symbol":"SOXX", "yf":"SOXX", "name":"iShares Semiconductor",   "exchange":"NASDAQ","cat":"Thematic"},
        {"symbol":"SMH",  "yf":"SMH",  "name":"VanEck Semiconductor",    "exchange":"NASDAQ","cat":"Thematic"},
        {"symbol":"IBB",  "yf":"IBB",  "name":"iShares Biotech",         "exchange":"NASDAQ","cat":"Thematic"},
        {"symbol":"XBI",  "yf":"XBI",  "name":"SPDR Biotech",            "exchange":"NYSE","cat":"Thematic"},
    ],
    "crypto": [
        {"symbol":"BTC-USD","yf":"BTC-USD","name":"Bitcoin",             "exchange":"CRYPTO","cat":"Layer 1"},
        {"symbol":"ETH-USD","yf":"ETH-USD","name":"Ethereum",            "exchange":"CRYPTO","cat":"Layer 1"},
        {"symbol":"BNB-USD","yf":"BNB-USD","name":"BNB",                 "exchange":"CRYPTO","cat":"Layer 1"},
        {"symbol":"SOL-USD","yf":"SOL-USD","name":"Solana",              "exchange":"CRYPTO","cat":"Layer 1"},
        {"symbol":"ADA-USD","yf":"ADA-USD","name":"Cardano",             "exchange":"CRYPTO","cat":"Layer 1"},
        {"symbol":"AVAX-USD","yf":"AVAX-USD","name":"Avalanche",         "exchange":"CRYPTO","cat":"Layer 1"},
        {"symbol":"DOT-USD","yf":"DOT-USD","name":"Polkadot",            "exchange":"CRYPTO","cat":"Layer 1"},
        {"symbol":"NEAR-USD","yf":"NEAR-USD","name":"NEAR Protocol",     "exchange":"CRYPTO","cat":"Layer 1"},
        {"symbol":"APT-USD","yf":"APT-USD","name":"Aptos",               "exchange":"CRYPTO","cat":"Layer 1"},
        {"symbol":"SUI-USD","yf":"SUI-USD","name":"Sui",                 "exchange":"CRYPTO","cat":"Layer 1"},
        {"symbol":"XRP-USD","yf":"XRP-USD","name":"XRP",                 "exchange":"CRYPTO","cat":"Payments"},
        {"symbol":"LTC-USD","yf":"LTC-USD","name":"Litecoin",            "exchange":"CRYPTO","cat":"Payments"},
        {"symbol":"BCH-USD","yf":"BCH-USD","name":"Bitcoin Cash",        "exchange":"CRYPTO","cat":"Payments"},
        {"symbol":"DOGE-USD","yf":"DOGE-USD","name":"Dogecoin",          "exchange":"CRYPTO","cat":"Meme"},
        {"symbol":"SHIB-USD","yf":"SHIB-USD","name":"Shiba Inu",         "exchange":"CRYPTO","cat":"Meme"},
        {"symbol":"PEPE-USD","yf":"PEPE-USD","name":"Pepe",              "exchange":"CRYPTO","cat":"Meme"},
        {"symbol":"WIF-USD","yf":"WIF-USD","name":"dogwifhat",           "exchange":"CRYPTO","cat":"Meme"},
        {"symbol":"LINK-USD","yf":"LINK-USD","name":"Chainlink",         "exchange":"CRYPTO","cat":"DeFi"},
        {"symbol":"UNI-USD","yf":"UNI-USD","name":"Uniswap",             "exchange":"CRYPTO","cat":"DeFi"},
        {"symbol":"AAVE-USD","yf":"AAVE-USD","name":"Aave",              "exchange":"CRYPTO","cat":"DeFi"},
        {"symbol":"OP-USD","yf":"OP-USD","name":"Optimism",              "exchange":"CRYPTO","cat":"L2"},
        {"symbol":"ARB-USD","yf":"ARB-USD","name":"Arbitrum",            "exchange":"CRYPTO","cat":"L2"},
        {"symbol":"MATIC-USD","yf":"MATIC-USD","name":"Polygon",         "exchange":"CRYPTO","cat":"L2"},
        {"symbol":"ATOM-USD","yf":"ATOM-USD","name":"Cosmos",            "exchange":"CRYPTO","cat":"Interop"},
    ],
    "forex": [
        # Majors
        {"symbol":"EURUSD","yf":"EURUSD=X","name":"Euro / US Dollar",        "exchange":"FX","cat":"Majors"},
        {"symbol":"GBPUSD","yf":"GBPUSD=X","name":"British Pound / US Dollar","exchange":"FX","cat":"Majors"},
        {"symbol":"USDJPY","yf":"USDJPY=X","name":"US Dollar / Japanese Yen","exchange":"FX","cat":"Majors"},
        {"symbol":"AUDUSD","yf":"AUDUSD=X","name":"Australian Dollar / USD",  "exchange":"FX","cat":"Majors"},
        {"symbol":"USDCAD","yf":"USDCAD=X","name":"US Dollar / Canadian Dollar","exchange":"FX","cat":"Majors"},
        {"symbol":"USDCHF","yf":"USDCHF=X","name":"US Dollar / Swiss Franc",  "exchange":"FX","cat":"Majors"},
        {"symbol":"NZDUSD","yf":"NZDUSD=X","name":"New Zealand Dollar / USD", "exchange":"FX","cat":"Majors"},
        # EUR Crosses
        {"symbol":"EURGBP","yf":"EURGBP=X","name":"Euro / British Pound",    "exchange":"FX","cat":"EUR Crosses"},
        {"symbol":"EURJPY","yf":"EURJPY=X","name":"Euro / Japanese Yen",     "exchange":"FX","cat":"EUR Crosses"},
        {"symbol":"EURCHF","yf":"EURCHF=X","name":"Euro / Swiss Franc",      "exchange":"FX","cat":"EUR Crosses"},
        {"symbol":"EURAUD","yf":"EURAUD=X","name":"Euro / Australian Dollar", "exchange":"FX","cat":"EUR Crosses"},
        {"symbol":"EURCAD","yf":"EURCAD=X","name":"Euro / Canadian Dollar",  "exchange":"FX","cat":"EUR Crosses"},
        {"symbol":"EURNZD","yf":"EURNZD=X","name":"Euro / New Zealand Dollar","exchange":"FX","cat":"EUR Crosses"},
        # GBP Crosses
        {"symbol":"GBPJPY","yf":"GBPJPY=X","name":"British Pound / Japanese Yen","exchange":"FX","cat":"GBP Crosses"},
        {"symbol":"GBPAUD","yf":"GBPAUD=X","name":"British Pound / AUD",     "exchange":"FX","cat":"GBP Crosses"},
        {"symbol":"GBPCAD","yf":"GBPCAD=X","name":"British Pound / CAD",     "exchange":"FX","cat":"GBP Crosses"},
        {"symbol":"GBPCHF","yf":"GBPCHF=X","name":"British Pound / CHF",     "exchange":"FX","cat":"GBP Crosses"},
        {"symbol":"GBPNZD","yf":"GBPNZD=X","name":"British Pound / NZD",     "exchange":"FX","cat":"GBP Crosses"},
        # Commodity Currencies
        {"symbol":"AUDJPY","yf":"AUDJPY=X","name":"Australian Dollar / JPY", "exchange":"FX","cat":"Commodity FX"},
        {"symbol":"AUDCAD","yf":"AUDCAD=X","name":"Australian Dollar / CAD", "exchange":"FX","cat":"Commodity FX"},
        {"symbol":"AUDCHF","yf":"AUDCHF=X","name":"Australian Dollar / CHF", "exchange":"FX","cat":"Commodity FX"},
        {"symbol":"AUDNZD","yf":"AUDNZD=X","name":"AUD / New Zealand Dollar","exchange":"FX","cat":"Commodity FX"},
        {"symbol":"CADJPY","yf":"CADJPY=X","name":"Canadian Dollar / JPY",   "exchange":"FX","cat":"Commodity FX"},
        {"symbol":"CADCHF","yf":"CADCHF=X","name":"Canadian Dollar / CHF",   "exchange":"FX","cat":"Commodity FX"},
        {"symbol":"NZDJPY","yf":"NZDJPY=X","name":"New Zealand Dollar / JPY","exchange":"FX","cat":"Commodity FX"},
        {"symbol":"CHFJPY","yf":"CHFJPY=X","name":"Swiss Franc / Japanese Yen","exchange":"FX","cat":"CHF Crosses"},
        # Exotics
        {"symbol":"USDTRY","yf":"USDTRY=X","name":"US Dollar / Turkish Lira","exchange":"FX","cat":"Exotics"},
        {"symbol":"USDZAR","yf":"USDZAR=X","name":"US Dollar / South African Rand","exchange":"FX","cat":"Exotics"},
        {"symbol":"USDMXN","yf":"USDMXN=X","name":"US Dollar / Mexican Peso","exchange":"FX","cat":"Exotics"},
        {"symbol":"USDSEK","yf":"USDSEK=X","name":"US Dollar / Swedish Krona","exchange":"FX","cat":"Exotics"},
        {"symbol":"USDNOK","yf":"USDNOK=X","name":"US Dollar / Norwegian Krone","exchange":"FX","cat":"Exotics"},
        {"symbol":"USDSGD","yf":"USDSGD=X","name":"US Dollar / Singapore Dollar","exchange":"FX","cat":"Exotics"},
        {"symbol":"USDHKD","yf":"USDHKD=X","name":"US Dollar / Hong Kong Dollar","exchange":"FX","cat":"Exotics"},
        {"symbol":"USDCNH","yf":"USDCNH=X","name":"US Dollar / Chinese Yuan",  "exchange":"FX","cat":"Exotics"},
        {"symbol":"USDINR","yf":"USDINR=X","name":"US Dollar / Indian Rupee",   "exchange":"FX","cat":"Exotics"},
        {"symbol":"USDBRL","yf":"USDBRL=X","name":"US Dollar / Brazilian Real", "exchange":"FX","cat":"Exotics"},
        {"symbol":"USDKRW","yf":"USDKRW=X","name":"US Dollar / South Korean Won","exchange":"FX","cat":"Exotics"},
    ],
    "metals": [
        {"symbol":"XAUUSD","yf":"GC=F",  "name":"Gold Spot (XAU/USD)",    "exchange":"OTC","cat":"Precious"},
        {"symbol":"XAGUSD","yf":"SI=F",  "name":"Silver Spot (XAG/USD)",  "exchange":"OTC","cat":"Precious"},
        {"symbol":"XPTUSD","yf":"PL=F",  "name":"Platinum (XPT/USD)",     "exchange":"OTC","cat":"Precious"},
        {"symbol":"XPDUSD","yf":"PA=F",  "name":"Palladium (XPD/USD)",    "exchange":"OTC","cat":"Precious"},
        {"symbol":"HG=F",  "yf":"HG=F",  "name":"Copper Futures",         "exchange":"COMEX","cat":"Base Metals"},
        {"symbol":"GC=F",  "yf":"GC=F",  "name":"Gold Futures (COMEX)",   "exchange":"COMEX","cat":"Precious"},
        {"symbol":"SI=F",  "yf":"SI=F",  "name":"Silver Futures (COMEX)", "exchange":"COMEX","cat":"Precious"},
    ],
    "energy": [
        {"symbol":"USOIL", "yf":"CL=F",  "name":"WTI Crude Oil (USOIL)",  "exchange":"OTC","cat":"Crude Oil"},
        {"symbol":"UKOIL", "yf":"BZ=F",  "name":"Brent Crude (UKOIL)",    "exchange":"OTC","cat":"Crude Oil"},
        {"symbol":"NATGAS","yf":"NG=F",  "name":"Natural Gas",             "exchange":"OTC","cat":"Gas"},
        {"symbol":"CL=F",  "yf":"CL=F",  "name":"WTI Crude Futures",      "exchange":"NYMEX","cat":"Crude Oil"},
        {"symbol":"BZ=F",  "yf":"BZ=F",  "name":"Brent Crude Futures",    "exchange":"ICE","cat":"Crude Oil"},
        {"symbol":"NG=F",  "yf":"NG=F",  "name":"Natural Gas Futures",    "exchange":"NYMEX","cat":"Gas"},
        {"symbol":"RB=F",  "yf":"RB=F",  "name":"RBOB Gasoline Futures",  "exchange":"NYMEX","cat":"Refined"},
        {"symbol":"HO=F",  "yf":"HO=F",  "name":"Heating Oil Futures",    "exchange":"NYMEX","cat":"Refined"},
    ],
    "agriculture": [
        {"symbol":"CORN",   "yf":"ZC=F", "name":"Corn",                   "exchange":"CBOT","cat":"Grains"},
        {"symbol":"WHEAT",  "yf":"ZW=F", "name":"Wheat",                  "exchange":"CBOT","cat":"Grains"},
        {"symbol":"SOYBEAN","yf":"ZS=F", "name":"Soybeans",               "exchange":"CBOT","cat":"Grains"},
        {"symbol":"ZC=F",   "yf":"ZC=F", "name":"Corn Futures",           "exchange":"CBOT","cat":"Grains"},
        {"symbol":"ZW=F",   "yf":"ZW=F", "name":"Wheat Futures",          "exchange":"CBOT","cat":"Grains"},
        {"symbol":"ZS=F",   "yf":"ZS=F", "name":"Soybean Futures",        "exchange":"CBOT","cat":"Grains"},
        {"symbol":"COFFEE", "yf":"KC=F", "name":"Coffee",                 "exchange":"ICE","cat":"Softs"},
        {"symbol":"SUGAR",  "yf":"SB=F", "name":"Sugar No. 11",           "exchange":"ICE","cat":"Softs"},
        {"symbol":"COTTON", "yf":"CT=F", "name":"Cotton No. 2",           "exchange":"ICE","cat":"Softs"},
        {"symbol":"COCOA",  "yf":"CC=F", "name":"Cocoa",                  "exchange":"ICE","cat":"Softs"},
        {"symbol":"KC=F",   "yf":"KC=F", "name":"Coffee Futures",         "exchange":"ICE","cat":"Softs"},
        {"symbol":"SB=F",   "yf":"SB=F", "name":"Sugar Futures",          "exchange":"ICE","cat":"Softs"},
    ],
    "indices": [
        # US
        {"symbol":"US500", "yf":"^GSPC", "name":"S&P 500",               "exchange":"INDEX","cat":"US"},
        {"symbol":"US100", "yf":"^NDX",  "name":"Nasdaq 100",            "exchange":"INDEX","cat":"US"},
        {"symbol":"US30",  "yf":"^DJI",  "name":"Dow Jones 30",          "exchange":"INDEX","cat":"US"},
        {"symbol":"US2000","yf":"^RUT",  "name":"Russell 2000",          "exchange":"INDEX","cat":"US"},
        {"symbol":"^GSPC", "yf":"^GSPC", "name":"S&P 500 Index",         "exchange":"INDEX","cat":"US"},
        {"symbol":"^NDX",  "yf":"^NDX",  "name":"Nasdaq 100 Index",      "exchange":"INDEX","cat":"US"},
        {"symbol":"^DJI",  "yf":"^DJI",  "name":"Dow Jones Index",       "exchange":"INDEX","cat":"US"},
        {"symbol":"^VIX",  "yf":"^VIX",  "name":"CBOE Volatility Index", "exchange":"INDEX","cat":"US"},
        # Europe
        {"symbol":"UK100", "yf":"^FTSE", "name":"FTSE 100",              "exchange":"INDEX","cat":"Europe"},
        {"symbol":"GER40", "yf":"^GDAXI","name":"DAX 40",                "exchange":"INDEX","cat":"Europe"},
        {"symbol":"FRA40", "yf":"^FCHI", "name":"CAC 40",                "exchange":"INDEX","cat":"Europe"},
        {"symbol":"ESP35", "yf":"^IBEX", "name":"IBEX 35",               "exchange":"INDEX","cat":"Europe"},
        {"symbol":"STOXX50","yf":"^STOXX50E","name":"Euro Stoxx 50",     "exchange":"INDEX","cat":"Europe"},
        {"symbol":"^FTSE", "yf":"^FTSE", "name":"FTSE 100",              "exchange":"INDEX","cat":"Europe"},
        {"symbol":"^GDAXI","yf":"^GDAXI","name":"DAX 40",                "exchange":"INDEX","cat":"Europe"},
        # Asia-Pacific
        {"symbol":"JPN225","yf":"^N225", "name":"Nikkei 225",            "exchange":"INDEX","cat":"Asia"},
        {"symbol":"HK50",  "yf":"^HSI",  "name":"Hang Seng 50",         "exchange":"INDEX","cat":"Asia"},
        {"symbol":"AUS200","yf":"^AXJO", "name":"ASX 200",               "exchange":"INDEX","cat":"Asia"},
        {"symbol":"^N225", "yf":"^N225", "name":"Nikkei 225",            "exchange":"INDEX","cat":"Asia"},
        {"symbol":"^HSI",  "yf":"^HSI",  "name":"Hang Seng Index",       "exchange":"INDEX","cat":"Asia"},
        {"symbol":"^KS11", "yf":"^KS11", "name":"KOSPI (South Korea)",   "exchange":"INDEX","cat":"Asia"},
        # EM
        {"symbol":"^BVSP", "yf":"^BVSP", "name":"Bovespa (Brazil)",      "exchange":"INDEX","cat":"EM"},
        {"symbol":"^BSESN","yf":"^BSESN","name":"BSE Sensex (India)",    "exchange":"INDEX","cat":"EM"},
        {"symbol":"^MXX",  "yf":"^MXX",  "name":"IPC Mexico",            "exchange":"INDEX","cat":"EM"},
    ],
    "futures": [
        # Equity Index Futures
        {"symbol":"ES=F",  "yf":"ES=F",  "name":"S&P 500 E-mini Futures","exchange":"CME","cat":"Index Futures"},
        {"symbol":"NQ=F",  "yf":"NQ=F",  "name":"Nasdaq 100 E-mini",     "exchange":"CME","cat":"Index Futures"},
        {"symbol":"YM=F",  "yf":"YM=F",  "name":"Dow Jones E-mini",      "exchange":"CME","cat":"Index Futures"},
        {"symbol":"RTY=F", "yf":"RTY=F", "name":"Russell 2000 E-mini",   "exchange":"CME","cat":"Index Futures"},
        # Bond Futures
        {"symbol":"ZN=F",  "yf":"ZN=F",  "name":"10-Year T-Note Futures","exchange":"CBOT","cat":"Rates"},
        {"symbol":"ZB=F",  "yf":"ZB=F",  "name":"30-Year T-Bond Futures","exchange":"CBOT","cat":"Rates"},
        {"symbol":"ZT=F",  "yf":"ZT=F",  "name":"2-Year T-Note Futures", "exchange":"CBOT","cat":"Rates"},
        # Volatility
        {"symbol":"VX=F",  "yf":"VX=F",  "name":"VIX Futures",           "exchange":"CBOE","cat":"Volatility"},
    ],
}

ALL_SYMBOLS = [s for cat in SYMBOLS.values() for s in cat]


# ── Bar ticker map: display symbol → yfinance ticker ─────────────────────────
_BAR_YF: dict[str, str] = {
    "NVDA":     "NVDA",     "TSLA":    "TSLA",      "AAPL":    "AAPL",
    "BTC":      "BTC-USD",  "ETH":     "ETH-USD",
    "EUR/USD":  "EURUSD=X", "GBP/USD": "GBPUSD=X",  "USD/JPY": "USDJPY=X",
    "GOLD":     "XAUUSD=X", "SILVER":  "XAGUSD=X",  "OIL(WTI)":"CL=F",
    "^VIX":     "^VIX",     "DXY":     "DX-Y.NYB",  "US10Y":   "^TNX",
    "SPY":      "SPY",      "QQQ":     "QQQ",
}

# Expected price ranges for sanity-checking yfinance fast_info results.
# If a value lands outside these bounds we know the feed is broken and we
# fall back to hourly history, which is more reliable for that symbol.
_PRICE_BOUNDS: dict[str, tuple[float, float]] = {
    "NVDA":     (10,    2000),   "TSLA":    (10,   2000),   "AAPL":    (50,    600),
    "BTC":      (5000, 250000),  "ETH":     (100, 30000),
    "EUR/USD":  (0.80,   1.60),  "GBP/USD": (0.90,  1.80),  "USD/JPY": (80,    200),
    "GOLD":     (1500,  8000),   "SILVER":  (8,     200),    "OIL(WTI)":(20,    200),
    "^VIX":     (5,      100),   "DXY":     (70,    130),    "US10Y":   (0.5,    15),
    "SPY":      (100,    900),   "QQQ":     (100,   800),
}

# Cache quotes for 60 seconds to avoid hammering yfinance on every request
_quotes_cache: list | None = None
_quotes_cache_ts: float = 0.0
_QUOTES_TTL = 30  # seconds


def _fetch_one(display: str, yf_sym: str):
    """Fetch a single ticker price for the market bar.

    Primary source: Yahoo Finance Chart REST API (regularMarketPrice).
    This is the live current price, completely independent of library bar-data
    or futures contract rolls — fixes gold/silver/DXY showing stale prices.

    Fallback: yfinance fast_info for equities, hourly history for everything else.
    """
    import yfinance as yf
    import urllib.request as _urlreq
    import urllib.parse   as _urlpar
    import json           as _json

    _NON_EQUITY = {"EUR/USD", "GBP/USD", "USD/JPY", "DXY", "US10Y",
                   "GOLD", "SILVER", "OIL(WTI)", "^VIX"}
    is_non_equity = (
        display in _NON_EQUITY
        or yf_sym.endswith("=F")
        or yf_sym.endswith("=X")
        or yf_sym.startswith("^")
    )

    lo, hi = _PRICE_BOUNDS.get(display, (0.0, float("inf")))

    def _rest_quote(sym: str) -> tuple[float, float] | None:
        """Yahoo Finance Chart API — regularMarketPrice is always the live price."""
        try:
            safe = _urlpar.quote(sym, safe="=^.")
            url  = (f"https://query1.finance.yahoo.com/v8/finance/chart/{safe}"
                    f"?interval=1m&range=1d")
            req  = _urlreq.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with _urlreq.urlopen(req, timeout=6) as r:
                meta = _json.loads(r.read())["chart"]["result"][0]["meta"]
                p    = float(meta.get("regularMarketPrice") or 0)
                prev = float(meta.get("chartPreviousClose") or
                             meta.get("previousClose") or 0)
                if p > 0 and prev > 0:
                    return p, prev
        except Exception:
            pass
        return None

    def _history_quote(t) -> tuple[float, float] | None:
        hist = t.history(period="5d", interval="1h")
        if hist is None or hist.empty:
            return None
        p  = float(hist["Close"].iloc[-1])
        pc = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else p
        return (p, pc) if p > 0 else None

    # Some =X tickers 404 on the REST API (e.g. XAUUSD=X) — use futures equivalent.
    _REST_MAP = {
        "XAUUSD=X": "GC=F",
        "XAGUSD=X": "SI=F",
        "XPTUSD=X": "PL=F",
        "XPDUSD=X": "PA=F",
    }

    # TradingView scanner: spot prices for metals (Yahoo only has futures)
    _TV_METALS: dict[str, tuple[str, str]] = {
        "XAUUSD=X": ("OANDA:XAUUSD", "cfd"),
        "XAGUSD=X": ("TVC:SILVER", "cfd"),
        "XPTUSD=X": ("TVC:PLATINUM", "cfd"),
        "XPDUSD=X": ("TVC:PALLADIUM", "cfd"),
    }

    def _tv_spot(sym: str) -> float | None:
        entry = _TV_METALS.get(sym)
        if not entry:
            return None
        tv_sym, screener = entry
        try:
            body = _json.dumps({
                "symbols": {"tickers": [tv_sym]},
                "columns": ["close"],
            }).encode()
            req = _urlreq.Request(
                f"https://scanner.tradingview.com/{screener}/scan",
                data=body,
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
            )
            with _urlreq.urlopen(req, timeout=8) as r:
                data = _json.loads(r.read())
            rows = data.get("data", [])
            if rows and rows[0].get("d"):
                return float(rows[0]["d"][0])
        except Exception:
            pass
        return None

    rest_sym = _REST_MAP.get(yf_sym, yf_sym)

    try:
        # 0. For metals, try TradingView scanner first (Yahoo only has futures prices)
        tv_price = _tv_spot(yf_sym)
        if tv_price and tv_price > 0 and lo <= tv_price <= hi:
            futures_result = _rest_quote(rest_sym)
            prev = futures_result[1] if futures_result else tv_price * 0.999
            result = (tv_price, prev)
        else:
            result = None

        # 1. If TV didn't work, try REST
        if result is None:
            result = _rest_quote(rest_sym)

        # 2. If REST failed or price is out of known bounds, fall back
        if result is None or not (lo <= result[0] <= hi):
            t = yf.Ticker(yf_sym)
            if is_non_equity:
                result = _history_quote(t)
            else:
                fi  = t.fast_info
                _p  = fi.last_price
                _pc = fi.previous_close
                if _p and _pc and float(_p) > 0 and float(_pc) > 0:
                    result = (float(_p), float(_pc))
                else:
                    result = _history_quote(t)

        if result is None:
            return None

        price, prev_close = result
        if price <= 0 or prev_close <= 0:
            return None

        # Final bounds guard
        if not (lo <= price <= hi):
            return None

        change     = price - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0.0

        if display in ("EUR/USD", "GBP/USD", "DXY"):
            price_fmt = round(price, 4)
        elif display == "USD/JPY":
            price_fmt = round(price, 2)
        elif display == "US10Y":
            price_fmt = round(price, 3)
        elif price > 1000:
            price_fmt = round(price, 0)
        else:
            price_fmt = round(price, 2)

        return {
            "symbol":    display,
            "price":     price_fmt,
            "change":    round(change, 4),
            "changePct": round(change_pct, 2),
        }
    except Exception:
        return None


@router.get("/quotes")
async def get_quotes():
    """
    Return real-time prices + day-change for the market bar tickers.
    Uses fast_info per-ticker (reliable across stocks, forex, futures, crypto).
    Cached for 60s to avoid yfinance rate limits.
    """
    global _quotes_cache, _quotes_cache_ts
    import time as _time

    if _quotes_cache and (_time.time() - _quotes_cache_ts) < _QUOTES_TTL:
        return _quotes_cache

    loop = asyncio.get_event_loop()
    tasks = [
        loop.run_in_executor(None, _fetch_one, display, yf_sym)
        for display, yf_sym in _BAR_YF.items()
    ]
    raw = await asyncio.gather(*tasks)
    results = [r for r in raw if r is not None]

    if results:
        _quotes_cache    = results
        _quotes_cache_ts = _time.time()
        return results

    return []   # empty → frontend uses seeds


@router.get("/symbols")
async def get_symbols(q: str = Query(default="", max_length=50)):
    """Search symbols by query string. Returns all if q is empty."""
    if not q:
        return {"symbols": ALL_SYMBOLS, "total": len(ALL_SYMBOLS)}
    q_lower = q.lower()
    results = [
        s for s in ALL_SYMBOLS
        if q_lower in s["symbol"].lower() or q_lower in s["name"].lower()
    ]
    return {"symbols": results[:30], "total": len(results)}


_COINGECKO_IDS = {
    "BTC-USD": "bitcoin", "ETH-USD": "ethereum", "SOL-USD": "solana",
    "BNB-USD": "binancecoin", "XRP-USD": "ripple", "ADA-USD": "cardano",
    "DOGE-USD": "dogecoin", "AVAX-USD": "avalanche-2", "MATIC-USD": "matic-network",
    "DOT-USD": "polkadot", "LINK-USD": "chainlink", "UNI-USD": "uniswap",
}


import time as _time

_ohlcv_cache: dict[str, tuple[dict, float]] = {}
_OHLCV_TTL: dict[str, int] = {
    "1m": 8, "5m": 12, "15m": 25, "30m": 25,
    "1h": 55, "4h": 110, "1d": 280, "1wk": 550,
}


@router.get("/ohlcv/{ticker}")
async def get_ohlcv(
    ticker: str,
    period: str = Query(default="6mo", regex="^(1d|5d|1mo|3mo|6mo|1y|2y)$"),
    interval: str = Query(default="1d", regex="^(1m|5m|15m|30m|1h|4h|1d|1wk)$"),
):
    """Return OHLCV candle data for the chart."""
    cache_key = f"{ticker}:{interval}:{period}"
    cached = _ohlcv_cache.get(cache_key)
    if cached and (_time.time() - cached[1]) < _OHLCV_TTL.get(interval, 60):
        return cached[0]

    def _cache_and_return(result):
        _ohlcv_cache[cache_key] = (result, _time.time())
        return result

    # ── 1. CoinGecko (primary source for crypto) ──────────────────────────────
    if ticker in _COINGECKO_IDS:
        try:
            coin_id = _COINGECKO_IDS[ticker]
            _PERIOD_TO_DAYS = {"1d": 1, "5d": 5, "1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "2y": 730}
            cg_days = _PERIOD_TO_DAYS.get(period, 180)
            url = (
                f"https://api.coingecko.com/api/v3/coins/{coin_id}"
                f"/ohlc?vs_currency=usd&days={cg_days}"
            )
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                raw = resp.json()  # [[timestamp_ms, open, high, low, close], ...]

            if raw:
                # Aggregate: group by day boundary (timestamp_ms / 1000 → seconds, round down to day)
                day_map: dict[int, dict] = {}
                for row in raw:
                    ts_ms, o, h, l, c = row
                    day_ts = int(ts_ms // 1000 // 86400 * 86400)
                    if day_ts not in day_map:
                        day_map[day_ts] = {"time": day_ts, "open": o, "high": h, "low": l, "close": c, "volume": 0}
                    else:
                        existing = day_map[day_ts]
                        existing["high"]  = max(existing["high"], h)
                        existing["low"]   = min(existing["low"], l)
                        existing["close"] = c  # last update wins for close

                candles = sorted(day_map.values(), key=lambda x: x["time"])
                return _cache_and_return({"ticker": ticker, "candles": candles})
        except Exception:
            pass  # fall through to yfinance

    # ── 2. yfinance + TradingView scanner spot-offset ───────────────────────
    # For metals: yfinance uses futures (GC=F) since Yahoo delisted spot =X.
    # We fetch real spot from TradingView scanner API and apply offset.
    try:
        import yfinance as yf
        import logging
        from app.data.market_data import (
            resolve_ticker, _SPOT_TO_FUTURES, _fetch_tv_ta_spot,
        )

        upper = ticker.upper()
        futures_sym = _SPOT_TO_FUTURES.get(upper)
        yf_ticker = futures_sym if futures_sym else resolve_ticker(ticker)
        logging.info(f"OHLCV step2: {ticker} → yf_ticker={yf_ticker}, futures={futures_sym}")

        def _sync():
            t = yf.Ticker(yf_ticker)
            hist = t.history(period=period, interval=interval, auto_adjust=True)
            if hist.empty:
                raise ValueError("empty")
            candles = []
            for ts, row in hist.iterrows():
                candles.append({
                    "time": int(ts.timestamp()),
                    "open":  round(float(row["Open"]), 4),
                    "high":  round(float(row["High"]), 4),
                    "low":   round(float(row["Low"]), 4),
                    "close": round(float(row["Close"]), 4),
                    "volume": int(row.get("Volume", 0)),
                })
            return candles

        candles = await asyncio.to_thread(_sync)
        logging.info(f"OHLCV step2: got {len(candles)} candles, last_close={candles[-1]['close'] if candles else 'N/A'}")

        # Apply spot-offset for futures-backed symbols
        if candles and futures_sym:
            spot = await _fetch_tv_ta_spot(ticker)
            logging.info(f"OHLCV step2: TV scanner spot for {ticker} = {spot}")
            if spot and spot > 0:
                last_close = candles[-1]["close"]
                offset = spot - last_close
                pct = abs(offset) / max(last_close, 1e-9)
                logging.info(f"OHLCV step2: offset={offset:.4f}, pct={pct:.4f}")
                if pct < 0.05:
                    for c in candles:
                        c["open"]  = round(c["open"] + offset, 4)
                        c["high"]  = round(c["high"] + offset, 4)
                        c["low"]   = round(c["low"] + offset, 4)
                        c["close"] = round(c["close"] + offset, 4)
                    logging.info(f"OHLCV step2: applied offset, new last_close={candles[-1]['close']}")
        elif candles:
            spot = await _fetch_tv_ta_spot(ticker)
            if spot and spot > 0:
                candles[-1]["close"] = round(spot, 4)
                candles[-1]["high"] = round(max(candles[-1]["high"], spot), 4)
                candles[-1]["low"] = round(min(candles[-1]["low"], spot), 4)

        return _cache_and_return({"ticker": ticker, "candles": candles})

    except Exception as yf_err:
        import logging
        logging.warning(f"yfinance OHLCV failed for {ticker}: {yf_err}")

    # ── 3. Yahoo Finance REST Chart API (fallback before mock) ───────────────
    try:
        import urllib.request as _urlreq
        import urllib.parse as _urlpar
        import json as _json
        from app.data.market_data import (
            resolve_ticker, _REST_ALIAS, _SPOT_TO_FUTURES, _fetch_tv_ta_spot,
        )

        upper = ticker.upper()
        futures_sym = _SPOT_TO_FUTURES.get(upper)
        rest_sym = futures_sym if futures_sym else resolve_ticker(ticker)
        if not futures_sym:
            alias = _REST_ALIAS.get(rest_sym)
            if alias:
                rest_sym = alias

        _INTERVAL_MAP = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "60m", "4h": "60m", "1d": "1d", "1wk": "1wk"}
        _RANGE_MAP = {"1d": "1d", "5d": "5d", "1mo": "1mo", "3mo": "3mo", "6mo": "6mo", "1y": "1y", "2y": "2y"}
        rest_interval = _INTERVAL_MAP.get(interval, "1d")
        rest_range = _RANGE_MAP.get(period, "6mo")

        def _rest_ohlcv():
            safe = _urlpar.quote(rest_sym, safe="=^.")
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{safe}?interval={rest_interval}&range={rest_range}"
            req = _urlreq.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with _urlreq.urlopen(req, timeout=15) as r:
                data = _json.loads(r.read())
            result = data["chart"]["result"][0]
            timestamps = result["timestamp"]
            quotes = result["indicators"]["quote"][0]
            candles = []
            for i, ts in enumerate(timestamps):
                o = quotes["open"][i]
                h = quotes["high"][i]
                l = quotes["low"][i]
                c = quotes["close"][i]
                # Yahoo returns "volume": null for some symbols and ranges.
                # `.get("volume", default)` does not help there - the key EXISTS
                # with value None, so the default never fires and None[i] raises.
                v = (quotes.get("volume") or [None] * len(timestamps))[i]
                if o is None or c is None:
                    continue
                candles.append({
                    "time": int(ts),
                    "open": round(float(o), 4),
                    "high": round(float(h), 4),
                    "low": round(float(l), 4),
                    "close": round(float(c), 4),
                    "volume": int(v) if v else 0,
                })
            if not candles:
                raise ValueError("no candles from REST")
            return candles

        candles = await asyncio.to_thread(_rest_ohlcv)

        if candles and futures_sym:
            spot = await _fetch_tv_ta_spot(ticker)
            if spot and spot > 0:
                last_close = candles[-1]["close"]
                offset = spot - last_close
                if abs(offset) < last_close * 0.05:
                    for c in candles:
                        c["open"]  = round(c["open"] + offset, 4)
                        c["high"]  = round(c["high"] + offset, 4)
                        c["low"]   = round(c["low"] + offset, 4)
                        c["close"] = round(c["close"] + offset, 4)

        return _cache_and_return({"ticker": ticker, "candles": candles})

    except Exception as rest_err:
        import logging
        logging.warning(f"Yahoo REST OHLCV also failed for {ticker}: {rest_err}")

    # ── 4. No data ───────────────────────────────────────────────────────────
    #
    # A mock fallback lived here. When TradingView, yfinance and the Yahoo REST
    # API had all failed it generated the chart from a hardcoded base price per
    # ticker and a random walk:
    #
    #     rng    = random.Random(sum(ord(c) for c in ticker))
    #     change = rng.gauss(0.0002, daily_vol)
    #     vol    = rng.uniform(5e5, 8e6)
    #
    # and returned it through the normal response shape, so the UI drew invented
    # candles as a price chart with no indication they were not real. A trader
    # reading support, resistance or a pattern off that chart is reading noise
    # seeded by the spelling of the symbol.
    #
    # An empty candle list is returned instead, with the reason attached, and
    # the chart shows that the feed is unavailable.
    return {
        "ticker": ticker,
        "candles": [],
        "error": "no_data",
        "detail": (f"No price data available for {ticker} - TradingView, yfinance "
                   f"and the Yahoo REST API all failed. No chart is drawn rather "
                   f"than a simulated one."),
    }


# ── 3D Microstructure Surface endpoints ──────────────────────────────────────
import math
import numpy as np
from collections import defaultdict as _ddict

_surface_cache: dict[str, tuple[dict, float]] = {}
_SURFACE_TTL = 3  # seconds


async def _get_ohlcv_for_surface(ticker: str, period: str = "5d", interval: str = "5m"):
    cached = _ohlcv_cache.get(f"{ticker}:{interval}:{period}")
    if cached and (_time.time() - cached[1]) < 30:
        return cached[0].get("candles", [])
    result = await get_ohlcv(ticker, period=period, interval=interval)
    return result.get("candles", [])


def _build_depth_surface(candles: list[dict], n_levels: int = 20, n_rows: int = 20) -> dict:
    if not candles or len(candles) < 5:
        return {"grid": [], "levels": [], "meta": {}}

    recent = candles[-n_rows * 3:] if len(candles) > n_rows * 3 else candles
    closes = [c["close"] for c in recent if c.get("close")]
    volumes = [c.get("volume", 1) for c in recent]
    if not closes:
        return {"grid": [], "levels": [], "meta": {}}

    mid = closes[-1]
    price_range = max(closes) - min(closes)
    if price_range <= 0:
        price_range = mid * 0.02

    half_range = price_range * 0.6
    price_min = mid - half_range
    price_max = mid + half_range
    step = (price_max - price_min) / (n_levels - 1) if n_levels > 1 else 1
    levels = [round(price_min + i * step, 5) for i in range(n_levels)]

    mid_idx = min(range(len(levels)), key=lambda i: abs(levels[i] - mid))

    grid = []
    chunk_size = max(1, len(recent) // n_rows)
    for row_i in range(n_rows):
        start = row_i * chunk_size
        chunk = recent[start:start + chunk_size]
        if not chunk:
            chunk = [recent[-1]]

        row_vol = sum(c.get("volume", 1) for c in chunk)
        avg_close = sum(c["close"] for c in chunk) / len(chunk)
        max_vol = max(volumes) if volumes else 1

        row = []
        for j, px in enumerate(levels):
            dist_from_price = abs(px - avg_close) / half_range
            vol_factor = 1.0 - min(dist_from_price, 1.0)
            vol_factor = vol_factor ** 1.5

            side_boost = 0.15 if px <= mid else 0.0
            depth_val = vol_factor * (row_vol / max(max_vol, 1)) + side_boost * vol_factor
            depth_val = min(1.0, max(0.0, depth_val))
            row.append(round(depth_val, 4))
        grid.append(row)

    bid_total = sum(grid[-1][:mid_idx])
    ask_total = sum(grid[-1][mid_idx:])

    return {
        "grid": grid,
        "levels": levels,
        "mid_price": mid,
        "bid_total": round(bid_total, 3),
        "ask_total": round(ask_total, 3),
        "meta": {
            "price_min": price_min,
            "price_max": price_max,
            "levels": n_levels,
            "mid": mid,
            "ts": _time.time(),
        },
    }


def _build_liquidity_surface(candles: list[dict], n_price_levels: int = 15, n_time_slices: int = 12) -> dict:
    if not candles or len(candles) < 3:
        return {"grid": [], "price_levels": [], "meta": {}}

    all_closes = [c["close"] for c in candles if c.get("close")]
    all_volumes = [c.get("volume", 1) for c in candles]
    if not all_closes:
        return {"grid": [], "price_levels": [], "meta": {}}

    price_min = min(all_closes)
    price_max = max(all_closes)
    price_range = price_max - price_min
    if price_range <= 0:
        price_range = price_min * 0.02
        price_min -= price_range / 2
        price_max += price_range / 2

    margin = price_range * 0.1
    price_min -= margin
    price_max += margin
    bucket_width = (price_max - price_min) / n_price_levels

    price_levels = [round(price_min + i * bucket_width, 5) for i in range(n_price_levels)]

    chunk_size = max(1, len(candles) // n_time_slices)
    grid = []
    max_volume = 0

    for slice_i in range(n_time_slices):
        start = slice_i * chunk_size
        chunk = candles[start:start + chunk_size]
        if not chunk:
            chunk = [candles[-1]]

        row = [0.0] * n_price_levels
        for c in chunk:
            px = c["close"]
            vol = c.get("volume", 1)
            bucket_idx = int((px - price_min) / bucket_width)
            bucket_idx = max(0, min(bucket_idx, n_price_levels - 1))
            row[bucket_idx] += vol
            if bucket_idx > 0:
                row[bucket_idx - 1] += vol * 0.3
            if bucket_idx < n_price_levels - 1:
                row[bucket_idx + 1] += vol * 0.3

        for v in row:
            if v > max_volume:
                max_volume = v
        grid.append(row)

    hotspot_price = price_levels[0]
    hotspot_vol = 0
    if grid:
        last_row = grid[-1]
        for i, v in enumerate(last_row):
            if v > hotspot_vol:
                hotspot_vol = v
                hotspot_price = price_levels[i]

    return {
        "grid": grid,
        "price_levels": price_levels,
        "max_volume": round(max_volume, 2),
        "hotspot_price": round(hotspot_price, 5),
        "meta": {
            "price_min": price_min,
            "price_max": price_max,
            "ts": _time.time(),
        },
    }


@router.get("/depth-surface/{ticker}")
async def get_depth_surface(ticker: str):
    cache_key = f"depth:{ticker}"
    cached = _surface_cache.get(cache_key)
    if cached and (_time.time() - cached[1]) < _SURFACE_TTL:
        return cached[0]

    candles = await _get_ohlcv_for_surface(ticker, period="5d", interval="5m")
    result = _build_depth_surface(candles, n_levels=20, n_rows=20)
    _surface_cache[cache_key] = (result, _time.time())
    return result


@router.get("/liquidity-surface/{ticker}")
async def get_liquidity_surface(ticker: str):
    cache_key = f"liq:{ticker}"
    cached = _surface_cache.get(cache_key)
    if cached and (_time.time() - cached[1]) < _SURFACE_TTL:
        return cached[0]

    candles = await _get_ohlcv_for_surface(ticker, period="1mo", interval="1h")
    result = _build_liquidity_surface(candles, n_price_levels=15, n_time_slices=12)
    _surface_cache[cache_key] = (result, _time.time())
    return result
