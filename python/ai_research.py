"""
Investment Thesis Lab - AI Research Module
Model-agnostic design: supports Claude (default), OpenAI, and future providers

This module helps transform investment ideas into actionable theses
using a structured research protocol aligned with the Wheel Strategy.
"""

import os
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


# ============================================================================
# Live Market Data Integration
# ============================================================================

# ============================================================================
# IBKR Data Integration (when connected)
# ============================================================================

_ibkr_client = None

def set_ibkr_client(ib_client):
    """Set the IBKR client for data enrichment"""
    global _ibkr_client
    _ibkr_client = ib_client
    logger.info("IBKR client set for research data enrichment")


def get_ibkr_stock_data(ticker: str) -> Dict[str, Any]:
    """
    Fetch stock data from IBKR API.
    Includes fundamental data, contract details, and real-time quotes.
    """
    if not _ibkr_client or not _ibkr_client.isConnected():
        return {"valid": False, "error": "IBKR not connected"}
    
    try:
        from ib_insync import Stock, Contract
        
        # Create stock contract
        contract = Stock(ticker, 'SMART', 'USD')
        _ibkr_client.qualifyContracts(contract)
        
        # Get contract details
        details = _ibkr_client.reqContractDetails(contract)
        if not details:
            return {"ticker": ticker, "valid": False, "error": "Contract not found"}
        
        detail = details[0]
        
        # Request market data snapshot
        _ibkr_client.reqMarketDataType(4)  # Delayed data if no subscription
        ticker_data = _ibkr_client.reqMktData(contract, '', True, False)
        _ibkr_client.sleep(2)  # Wait for data
        
        # Check for options
        try:
            chains = _ibkr_client.reqSecDefOptParams(
                contract.symbol, '', contract.secType, contract.conId
            )
            has_options = len(chains) > 0 if chains else False
        except:
            has_options = False
        
        # Get fundamental data (requires Reuters subscription)
        fundamental_data = {}
        try:
            ratios = _ibkr_client.reqFundamentalData(contract, 'ReportSnapshot')
            if ratios:
                fundamental_data['has_fundamentals'] = True
        except:
            fundamental_data['has_fundamentals'] = False
        
        current_price = ticker_data.last if ticker_data.last else ticker_data.close
        
        return {
            "ticker": ticker,
            "valid": True,
            "source": "IBKR",
            "name": detail.longName,
            "current_price": current_price,
            "bid": ticker_data.bid,
            "ask": ticker_data.ask,
            "volume": ticker_data.volume,
            "has_options": has_options,
            "industry": detail.industry,
            "category": detail.category,
            "subcategory": detail.subcategory,
            "market_cap_tier": "Unknown",  # IBKR doesn't provide this directly
            "tradeable": True,
            **fundamental_data
        }
        
    except Exception as e:
        logger.warning(f"IBKR data fetch failed for {ticker}: {e}")
        return {"ticker": ticker, "valid": False, "error": str(e), "source": "IBKR"}


def get_ibkr_scanner_results(scan_code: str = "TOP_PERC_GAIN", num_results: int = 20) -> List[Dict]:
    """
    Run an IBKR market scanner.
    
    Scan codes include:
    - TOP_PERC_GAIN: Biggest % gainers
    - TOP_PERC_LOSE: Biggest % losers  
    - MOST_ACTIVE: Most active by volume
    - HOT_BY_VOLUME: Hot by volume
    - HIGH_OPT_IMP_VOLAT: High option implied volatility
    - HIGH_OPT_VOLUME_PUT_CALL_RATIO: High put/call ratio
    """
    if not _ibkr_client or not _ibkr_client.isConnected():
        return []
    
    try:
        from ib_insync import ScannerSubscription
        
        sub = ScannerSubscription(
            instrument='STK',
            locationCode='STK.US.MAJOR',
            scanCode=scan_code,
            numberOfRows=num_results
        )
        
        results = _ibkr_client.reqScannerData(sub)
        
        return [{
            "rank": r.rank,
            "ticker": r.contractDetails.contract.symbol,
            "name": r.contractDetails.longName,
            "distance": r.distance
        } for r in results]
        
    except Exception as e:
        logger.warning(f"IBKR scanner failed: {e}")
        return []


def get_live_stock_data(ticker: str) -> Dict[str, Any]:
    """
    Fetch live market data for a ticker using yfinance.
    Returns current price, market cap, options availability, etc.
    """
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Check if we got valid data
        if not info or not info.get('symbol'):
            return {"ticker": ticker, "valid": False, "error": "Ticker not found"}
        
        # Get options expiration dates to check if options are available
        try:
            options_dates = stock.options
            has_options = len(options_dates) > 0 if options_dates else False
        except:
            has_options = False
        
        # Calculate some basic metrics
        current_price = info.get('currentPrice') or info.get('regularMarketPrice')
        market_cap = info.get('marketCap', 0)
        
        # Determine market cap tier
        if market_cap >= 200_000_000_000:
            cap_tier = "Mega"
        elif market_cap >= 10_000_000_000:
            cap_tier = "Large"
        elif market_cap >= 2_000_000_000:
            cap_tier = "Mid"
        elif market_cap >= 300_000_000:
            cap_tier = "Small"
        else:
            cap_tier = "Micro"
        
        return {
            "ticker": ticker,
            "valid": True,
            "name": info.get('shortName') or info.get('longName', ticker),
            "current_price": current_price,
            "market_cap": market_cap,
            "market_cap_tier": cap_tier,
            "has_options": has_options,
            "sector": info.get('sector', 'Unknown'),
            "industry": info.get('industry', 'Unknown'),
            "52w_high": info.get('fiftyTwoWeekHigh'),
            "52w_low": info.get('fiftyTwoWeekLow'),
            "avg_volume": info.get('averageVolume'),
            "beta": info.get('beta'),
            "pe_ratio": info.get('trailingPE'),
            "dividend_yield": info.get('dividendYield'),
            "description": info.get('longBusinessSummary', '')[:200] + '...' if info.get('longBusinessSummary') else ''
        }
    except Exception as e:
        logger.warning(f"Failed to fetch data for {ticker}: {e}")
        return {
            "ticker": ticker,
            "valid": False,
            "error": str(e)
        }


def enrich_companies_with_live_data(companies: List[Dict], use_ibkr: bool = True) -> List[Dict]:
    """
    Enrich a list of companies with live market data.
    Prefers IBKR when connected, falls back to Yahoo Finance.
    """
    import time
    enriched = []
    data_source = "unknown"
    
    # Check if IBKR is available
    ibkr_available = use_ibkr and _ibkr_client and _ibkr_client.isConnected()
    if ibkr_available:
        data_source = "IBKR (live)"
        logger.info("Using IBKR for data enrichment")
    else:
        data_source = "yfinance (live)"
        logger.info("Using yfinance for data enrichment (IBKR not connected)")
    
    for i, company in enumerate(companies):
        ticker = company.get('ticker', '')
        if ticker:
            # Rate limit for yfinance
            if not ibkr_available and i > 0:
                time.sleep(0.3)
            
            # Try IBKR first, fall back to yfinance
            if ibkr_available:
                live_data = get_ibkr_stock_data(ticker)
                # If IBKR fails, try yfinance
                if not live_data.get('valid'):
                    live_data = get_live_stock_data(ticker)
            else:
                live_data = get_live_stock_data(ticker)
            
            if live_data.get('valid'):
                company['live_data'] = live_data
                company['verified'] = True
                company['data_source'] = live_data.get('source', 'yfinance')
                # Update with real data
                company['market_cap_tier'] = live_data.get('market_cap_tier', company.get('market_cap_tier'))
                company['has_options'] = live_data.get('has_options', False)
                company['current_price'] = live_data.get('current_price')
                company['bid'] = live_data.get('bid')
                company['ask'] = live_data.get('ask')
            else:
                company['verified'] = False
                company['verification_error'] = live_data.get('error')
        enriched.append(company)
    
    return enriched


def search_tickers_by_keyword(keyword: str, limit: int = 20) -> List[Dict]:
    """
    Search for tickers related to a keyword using yfinance.
    """
    try:
        import yfinance as yf
        # yfinance doesn't have a direct search, but we can use the Ticker class
        # This is a workaround - in production you'd use a proper search API
        search = yf.Ticker(keyword)
        # If it's a valid ticker, return it
        if search.info.get('symbol'):
            return [get_live_stock_data(keyword)]
        return []
    except:
        return []

# Default provider can be set via environment variable
# Options: "auto", "claude", "openai"
DEFAULT_PROVIDER = os.getenv("AI_PROVIDER", "auto")

# Fallback models if API fetch fails
FALLBACK_MODELS = {
    "claude": [
        {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4", "description": "Fast, excellent for research"},
        {"id": "claude-opus-4-20250514", "name": "Claude Opus 4", "description": "Most powerful, deep analysis"},
    ],
    "openai": [
        {"id": "gpt-4o", "name": "GPT-4o", "description": "Latest multimodal, fast"},
        {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "description": "Faster, cost-efficient"},
    ]
}

# Cache for fetched models (refreshed periodically)
_models_cache: Dict[str, Any] = {"claude": None, "openai": None, "last_fetch": None}
_CACHE_TTL = 3600  # Refresh every hour


def _fetch_claude_models() -> list:
    """Fetch available models from Anthropic API"""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return []
    
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        
        # Anthropic's models.list() endpoint
        response = client.models.list()
        
        models = []
        for model in response.data:
            # Filter for chat models (claude-*)
            if model.id.startswith("claude"):
                # Create friendly name from model ID
                name = model.id.replace("-", " ").title()
                # Simplify common patterns
                name = name.replace("Claude ", "Claude ")
                
                models.append({
                    "id": model.id,
                    "name": model.display_name if hasattr(model, 'display_name') else name,
                    "description": getattr(model, 'description', 'Anthropic model'),
                    "created": getattr(model, 'created_at', None)
                })
        
        # Sort by created date (newest first) if available
        models.sort(key=lambda x: x.get('created') or '', reverse=True)
        
        # Limit to top models for usability
        return models[:10] if len(models) > 10 else models
        
    except Exception as e:
        logger.warning(f"Failed to fetch Claude models: {e}")
        return FALLBACK_MODELS.get("claude", [])


def _fetch_openai_models() -> list:
    """Fetch available models from OpenAI API"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return []
    
    try:
        import openai
        # Create client without proxy settings
        client = openai.OpenAI(api_key=api_key, http_client=None)
        
        # OpenAI's models.list() endpoint
        response = client.models.list()
        
        # Filter for chat-capable models
        chat_prefixes = ('gpt-4', 'gpt-3.5', 'o1', 'o3', 'chatgpt')
        exclude_patterns = ('instruct', 'vision', 'audio', 'realtime', 'search', 'edit', 'embed', 'tts', 'whisper', 'dall')
        
        models = []
        for model in response.data:
            model_id = model.id.lower()
            
            # Include if starts with chat prefix
            if any(model_id.startswith(p) for p in chat_prefixes):
                # Exclude non-chat variants
                if any(excl in model_id for excl in exclude_patterns):
                    continue
                
                # Create friendly name
                name = model.id.replace("-", " ").title()
                name = name.replace("Gpt ", "GPT-")
                
                models.append({
                    "id": model.id,
                    "name": name,
                    "description": f"OpenAI {model.id}",
                    "created": model.created
                })
        
        # Sort by created date (newest first)
        models.sort(key=lambda x: x.get('created') or 0, reverse=True)
        
        # Limit to top models for usability
        return models[:10] if len(models) > 10 else models
        
    except Exception as e:
        logger.warning(f"Failed to fetch OpenAI models: {e}")
        return FALLBACK_MODELS.get("openai", [])


def get_available_models(force_refresh: bool = False) -> Dict[str, list]:
    """
    Get available models from both providers.
    Fetches live from APIs, with caching and fallback.
    """
    global _models_cache
    
    now = datetime.now()
    cache_age = (now - _models_cache["last_fetch"]).total_seconds() if _models_cache["last_fetch"] else float('inf')
    
    # Use cache if fresh enough
    if not force_refresh and cache_age < _CACHE_TTL:
        result = {}
        if _models_cache["claude"]:
            result["claude"] = _models_cache["claude"]
        if _models_cache["openai"]:
            result["openai"] = _models_cache["openai"]
        if result:
            return result
    
    # Fetch fresh models
    available = {}
    
    if os.getenv("ANTHROPIC_API_KEY"):
        claude_models = _fetch_claude_models()
        if claude_models:
            _models_cache["claude"] = claude_models
            available["claude"] = claude_models
    
    if os.getenv("OPENAI_API_KEY"):
        openai_models = _fetch_openai_models()
        if openai_models:
            _models_cache["openai"] = openai_models
            available["openai"] = openai_models
    
    _models_cache["last_fetch"] = now
    
    return available


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class ResearchRequest:
    """An investment idea to research"""
    ticker: str
    idea: str  # What sparked the idea?
    sector: Optional[str] = None
    thesis_type: str = "wheel"  # wheel, covered_call, long_term


@dataclass
class CompetitorProfile:
    """Competitor analysis"""
    name: str
    ticker: Optional[str]
    market_position: str
    strengths: List[str]
    weaknesses: List[str]


@dataclass 
class FinancialHealth:
    """Financial health assessment"""
    debt_to_equity: Optional[float]
    current_ratio: Optional[float]
    free_cash_flow: str
    revenue_growth: str
    profit_margins: str
    dividend_yield: Optional[float]
    overall_rating: str  # Strong, Moderate, Weak


@dataclass
class WheelFit:
    """Wheel strategy fit assessment"""
    score: int  # 1-10
    ideal_strike_range: str
    suggested_dte: int
    premium_potential: str  # Low, Medium, High
    assignment_risk: str
    reasons_for: List[str]
    reasons_against: List[str]


@dataclass
class InvestmentThesis:
    """Complete investment thesis"""
    ticker: str
    company_name: str
    sector: str
    summary: str  # 2-3 sentence thesis
    
    # Market Position
    market_overview: str
    competitors: List[CompetitorProfile]
    competitive_moat: str
    
    # Financials
    financial_health: FinancialHealth
    
    # Risk Assessment
    bull_case: str
    bear_case: str
    key_risks: List[str]
    catalysts: List[str]
    
    # Wheel Strategy Fit
    wheel_fit: WheelFit
    
    # Verdict
    verdict: str  # STRONG BUY, BUY, HOLD, AVOID
    confidence: int  # 1-100
    
    # Metadata
    research_date: str
    model_used: str


# ============================================================================
# AI Provider Interface (Model-Agnostic)
# ============================================================================

class AIProvider(ABC):
    """Abstract base class for AI providers"""
    
    @abstractmethod
    def get_name(self) -> str:
        """Return provider name"""
        pass
    
    @abstractmethod
    def get_model_id(self) -> str:
        """Return the current model ID"""
        pass
    
    @abstractmethod
    def set_model(self, model_id: str) -> None:
        """Set the model to use"""
        pass
    
    @abstractmethod
    def chat(self, system_prompt: str, user_message: str) -> str:
        """Send a message and get a response"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is configured and available"""
        pass


class ClaudeProvider(AIProvider):
    """Claude (Anthropic) provider - Default"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self._client = None
    
    @property
    def client(self):
        if self._client is None and self.api_key:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                logger.error("anthropic package not installed. Run: pip install anthropic")
        return self._client
    
    def get_name(self) -> str:
        # Find friendly name from cached models or generate from ID
        if _models_cache.get("claude"):
            for m in _models_cache["claude"]:
                if m["id"] == self.model:
                    return m["name"]
        # Generate friendly name from model ID
        name = self.model.replace("-", " ").replace("claude ", "Claude ").title()
        return name
    
    def get_model_id(self) -> str:
        return self.model
    
    def set_model(self, model_id: str) -> None:
        self.model = model_id
        logger.info(f"Claude model set to: {model_id}")
    
    def is_available(self) -> bool:
        return self.client is not None
    
    def chat(self, system_prompt: str, user_message: str) -> str:
        if not self.is_available():
            raise RuntimeError("Claude provider not available. Check API key.")
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )
        return response.content[0].text


class OpenAIProvider(AIProvider):
    """OpenAI provider - Alternative"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self._client = None
    
    @property
    def client(self):
        if self._client is None and self.api_key:
            try:
                import openai
                self._client = openai.OpenAI(api_key=self.api_key)
            except ImportError:
                logger.error("openai package not installed. Run: pip install openai")
        return self._client
    
    def get_name(self) -> str:
        # Find friendly name from cached models or generate from ID
        if _models_cache.get("openai"):
            for m in _models_cache["openai"]:
                if m["id"] == self.model:
                    return m["name"]
        # Generate friendly name from model ID
        name = self.model.replace("-", " ").replace("gpt ", "GPT-").title()
        return name
    
    def get_model_id(self) -> str:
        return self.model
    
    def set_model(self, model_id: str) -> None:
        self.model = model_id
        logger.info(f"OpenAI model set to: {model_id}")
    
    def is_available(self) -> bool:
        return self.client is not None
    
    def chat(self, system_prompt: str, user_message: str) -> str:
        if not self.is_available():
            raise RuntimeError("OpenAI provider not available. Check API key.")
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
        )
        return response.choices[0].message.content


# ============================================================================
# Research Protocol
# ============================================================================

WHEEL_RESEARCH_PROTOCOL = """You are an expert investment analyst specializing in options strategies, 
particularly the Wheel Strategy (selling cash-secured puts and covered calls).

Your role is to help transform investment ideas into actionable theses.

## Research Protocol

When analyzing a stock for the Wheel Strategy, evaluate:

### 1. Company Fundamentals
- What does the company do? What's their competitive advantage?
- Revenue growth and profitability trends
- Debt levels and financial stability
- Management quality and track record

### 2. Market Position
- Market share and industry position
- Competitive landscape (who are the main competitors?)
- Industry tailwinds or headwinds

### 3. Wheel Strategy Fit
For the Wheel Strategy, the ideal stock:
- Has a price you'd be comfortable owning (you might get assigned)
- Trades between $20-$300 (good premium, reasonable capital requirements)
- Has weekly options for flexibility
- Has IV Rank > 30% for decent premium
- Isn't approaching earnings (unless intentional)
- Has stable to bullish outlook

### 4. Risk Assessment
- What could go wrong? (Bear case)
- What catalysts could drive the stock higher? (Bull case)
- Key risks to monitor

## Output Format

Always respond in valid JSON format matching the requested schema.
Be specific with numbers and analysis. Avoid generic statements.
If you don't know something, say so rather than guessing.
"""


# ============================================================================
# Research Engine
# ============================================================================

class InvestmentResearchEngine:
    """Main research engine for the Investment Thesis Lab"""
    
    def __init__(self, provider: Optional[AIProvider] = None):
        """
        Initialize with a specific provider or auto-detect.
        Default order: Claude > OpenAI
        """
        if provider:
            self.provider = provider
        else:
            # Auto-detect available provider
            self.provider = self._auto_detect_provider()
    
    def _auto_detect_provider(self) -> AIProvider:
        """Auto-detect the best available provider based on config"""
        
        # Check if a specific provider is requested
        if DEFAULT_PROVIDER == "claude":
            claude = ClaudeProvider()
            if claude.is_available():
                logger.info("Using Claude as AI provider (configured)")
                return claude
            raise RuntimeError("Claude configured but ANTHROPIC_API_KEY not set")
        
        elif DEFAULT_PROVIDER == "openai":
            openai_provider = OpenAIProvider()
            if openai_provider.is_available():
                logger.info("Using OpenAI as AI provider (configured)")
                return openai_provider
            raise RuntimeError("OpenAI configured but OPENAI_API_KEY not set")
        
        # Auto mode: Try Claude first (default), then OpenAI
        claude = ClaudeProvider()
        if claude.is_available():
            logger.info("Using Claude as AI provider (auto-detected)")
            return claude
        
        openai_provider = OpenAIProvider()
        if openai_provider.is_available():
            logger.info("Using OpenAI as AI provider (auto-detected)")
            return openai_provider
        
        raise RuntimeError(
            "No AI provider available. Please set ANTHROPIC_API_KEY or OPENAI_API_KEY in your .env file"
        )
    
    def switch_provider(self, provider: str, model_id: Optional[str] = None) -> None:
        """Switch to a different provider/model at runtime"""
        if provider == "claude":
            new_provider = ClaudeProvider(model=model_id or "claude-sonnet-4-20250514")
        elif provider == "openai":
            new_provider = OpenAIProvider(model=model_id or "gpt-4o")
        else:
            raise ValueError(f"Unknown provider: {provider}")
        
        if not new_provider.is_available():
            raise RuntimeError(f"{provider} provider not available - check API key")
        
        self.provider = new_provider
        logger.info(f"Switched to {self.provider.get_name()}")
    
    def switch_model(self, model_id: str) -> None:
        """Switch to a different model within the current provider"""
        self.provider.set_model(model_id)
        logger.info(f"Model switched to: {model_id}")
    
    def get_provider_name(self) -> str:
        return self.provider.get_name()
    
    def research_idea(self, request: ResearchRequest) -> InvestmentThesis:
        """
        Research an investment idea and return a complete thesis.
        """
        prompt = f"""
Research the following investment idea and provide a complete analysis:

**Ticker:** {request.ticker}
**Investment Idea:** {request.idea}
**Sector:** {request.sector or "Unknown - please identify"}
**Strategy Focus:** {request.thesis_type}

Please analyze this opportunity and return your findings as a JSON object with this structure:

{{
    "ticker": "{request.ticker}",
    "company_name": "Full company name",
    "sector": "Industry sector",
    "summary": "2-3 sentence investment thesis",
    
    "market_overview": "Overview of the market and company's position",
    "competitors": [
        {{
            "name": "Competitor name",
            "ticker": "TICK or null",
            "market_position": "How they compete",
            "strengths": ["strength1", "strength2"],
            "weaknesses": ["weakness1", "weakness2"]
        }}
    ],
    "competitive_moat": "What protects this company's market position",
    
    "financial_health": {{
        "debt_to_equity": 0.5,
        "current_ratio": 1.5,
        "free_cash_flow": "Strong/Moderate/Weak with explanation",
        "revenue_growth": "X% YoY with trend",
        "profit_margins": "X% with context",
        "dividend_yield": 2.5,
        "overall_rating": "Strong/Moderate/Weak"
    }},
    
    "bull_case": "Why the stock could go up",
    "bear_case": "Why the stock could go down",
    "key_risks": ["risk1", "risk2", "risk3"],
    "catalysts": ["catalyst1", "catalyst2"],
    
    "wheel_fit": {{
        "score": 8,
        "ideal_strike_range": "$X - $Y",
        "suggested_dte": 30,
        "premium_potential": "High/Medium/Low",
        "assignment_risk": "Assessment of assignment probability",
        "reasons_for": ["reason1", "reason2"],
        "reasons_against": ["reason1"]
    }},
    
    "verdict": "STRONG BUY/BUY/HOLD/AVOID",
    "confidence": 75
}}

Important: Return ONLY the JSON object, no markdown formatting or additional text.
"""
        
        response = self.provider.chat(WHEEL_RESEARCH_PROTOCOL, prompt)
        
        # Parse the response
        try:
            # Clean up response if it has markdown
            clean_response = response.strip()
            if clean_response.startswith("```"):
                clean_response = clean_response.split("```")[1]
                if clean_response.startswith("json"):
                    clean_response = clean_response[4:]
            
            data = json.loads(clean_response)
            
            # Build the thesis object
            thesis = InvestmentThesis(
                ticker=data["ticker"],
                company_name=data["company_name"],
                sector=data["sector"],
                summary=data["summary"],
                market_overview=data["market_overview"],
                competitors=[
                    CompetitorProfile(**c) for c in data.get("competitors", [])
                ],
                competitive_moat=data["competitive_moat"],
                financial_health=FinancialHealth(**data["financial_health"]),
                bull_case=data["bull_case"],
                bear_case=data["bear_case"],
                key_risks=data["key_risks"],
                catalysts=data["catalysts"],
                wheel_fit=WheelFit(**data["wheel_fit"]),
                verdict=data["verdict"],
                confidence=data["confidence"],
                research_date=datetime.now().isoformat(),
                model_used=self.provider.get_name()
            )
            
            return thesis
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse AI response: {e}")
            logger.debug(f"Raw response: {response}")
            raise ValueError(f"Failed to parse research response: {e}")
    
    def quick_screen(self, ticker: str) -> Dict[str, Any]:
        """
        Quick screen a ticker for Wheel Strategy fit.
        Returns a simple go/no-go assessment.
        """
        prompt = f"""
Quick screen {ticker} for the Wheel Strategy. 

Return a JSON object with:
{{
    "ticker": "{ticker}",
    "current_price": "approximate current price",
    "wheel_suitable": true/false,
    "score": 1-10,
    "summary": "One sentence verdict",
    "key_concern": "Main risk if any",
    "premium_estimate": "Estimated 30-day ATM put premium %"
}}

Only return the JSON, no additional text.
"""
        
        response = self.provider.chat(WHEEL_RESEARCH_PROTOCOL, prompt)
        
        try:
            clean_response = response.strip()
            if clean_response.startswith("```"):
                clean_response = clean_response.split("```")[1]
                if clean_response.startswith("json"):
                    clean_response = clean_response[4:]
            return json.loads(clean_response)
        except json.JSONDecodeError:
            return {"error": "Failed to parse response", "raw": response}
    
    def discover_companies(self, thesis: str, max_results: int = 10) -> Dict[str, Any]:
        """
        Discover companies based on an investment thesis or sector idea.
        Goes from concept → specific companies to research.
        """
        prompt = f"""
I have an investment thesis or sector idea I want to explore:

"{thesis}"

Please help me discover companies in this space. I need:

1. **Market Overview**: Brief explanation of this sector/thesis (2-3 sentences)
2. **Key Players**: List of companies (public, tradeable) that are relevant to this thesis
3. **For each company**, provide:
   - Ticker symbol
   - Company name
   - Market cap tier (Large/Mid/Small/Micro)
   - How they fit the thesis (1 sentence)
   - Wheel Strategy suitability (1-10)

Return as JSON:
{{
    "thesis_summary": "Brief summary of the investment thesis",
    "market_overview": "2-3 sentence overview of the sector",
    "total_addressable_market": "Estimated TAM if known",
    "growth_outlook": "High/Medium/Low with brief reason",
    "companies": [
        {{
            "ticker": "SYMBOL",
            "name": "Company Name",
            "market_cap_tier": "Large/Mid/Small/Micro",
            "thesis_fit": "How they fit the thesis",
            "wheel_score": 7,
            "key_catalyst": "Main reason to watch this stock",
            "key_risk": "Main risk"
        }}
    ],
    "etfs": [
        {{
            "ticker": "ETF",
            "name": "ETF Name", 
            "description": "What it covers"
        }}
    ],
    "emerging_players": ["Private companies or pre-IPO to watch"],
    "recommended_focus": "Which 2-3 companies are best for Wheel Strategy and why"
}}

Focus on:
- Publicly traded US stocks (tradeable options preferred)
- Companies with direct exposure to the thesis
- Include both pure-plays and larger companies with significant exposure
- Sort by relevance to the thesis
- IMPORTANT: Many companies have gone public via SPAC or IPO recently - assume companies in hot sectors (AI, nuclear, space, etc.) may now be public even if they were private previously
- When in doubt, include the company in the main list with a note that it may have recently IPO'd

Only return the JSON, no additional text.
"""
        
        response = self.provider.chat(WHEEL_RESEARCH_PROTOCOL, prompt)
        
        try:
            clean_response = response.strip()
            if clean_response.startswith("```"):
                clean_response = clean_response.split("```")[1]
                if clean_response.startswith("json"):
                    clean_response = clean_response[4:]
            result = json.loads(clean_response)
            
            # Enrich with live market data
            if result.get('companies'):
                logger.info(f"Enriching {len(result['companies'])} companies with live data...")
                result['companies'] = enrich_companies_with_live_data(result['companies'])
                
                # Add summary of verification
                verified_count = sum(1 for c in result['companies'] if c.get('verified'))
                with_options = sum(1 for c in result['companies'] if c.get('has_options'))
                result['data_enrichment'] = {
                    'verified_tickers': verified_count,
                    'total_tickers': len(result['companies']),
                    'with_options': with_options,
                    'source': 'yfinance (live)'
                }
            
            return result
        except json.JSONDecodeError:
            return {"error": "Failed to parse response", "raw": response}

    def compare_opportunities(self, tickers: List[str]) -> Dict[str, Any]:
        """
        Compare multiple tickers for Wheel Strategy deployment.
        """
        tickers_str = ", ".join(tickers)
        prompt = f"""
Compare these stocks for Wheel Strategy deployment: {tickers_str}

Return a JSON object with:
{{
    "comparison": [
        {{
            "ticker": "TICK",
            "wheel_score": 1-10,
            "premium_potential": "High/Medium/Low",
            "risk_level": "High/Medium/Low",
            "summary": "One sentence"
        }}
    ],
    "recommendation": "Which one is best and why",
    "ranking": ["BEST", "SECOND", "THIRD", ...]
}}

Only return the JSON, no additional text.
"""
        
        response = self.provider.chat(WHEEL_RESEARCH_PROTOCOL, prompt)
        
        try:
            clean_response = response.strip()
            if clean_response.startswith("```"):
                clean_response = clean_response.split("```")[1]
                if clean_response.startswith("json"):
                    clean_response = clean_response[4:]
            return json.loads(clean_response)
        except json.JSONDecodeError:
            return {"error": "Failed to parse response", "raw": response}
    
    def chat(self, message: str, context: Optional[str] = None) -> str:
        """
        Open-ended chat with the research AI.
        Useful for follow-up questions or deeper analysis.
        """
        system = WHEEL_RESEARCH_PROTOCOL
        if context:
            system += f"\n\nPrevious Context:\n{context}"
        
        return self.provider.chat(system, message)


# ============================================================================
# Factory Function
# ============================================================================

def get_research_engine(provider: str = "auto", api_key: Optional[str] = None) -> InvestmentResearchEngine:
    """
    Factory function to create a research engine with the specified provider.
    
    Args:
        provider: "auto", "claude", or "openai"
        api_key: Optional API key (otherwise uses environment variable)
    
    Returns:
        InvestmentResearchEngine configured with the specified provider
    """
    if provider == "auto":
        return InvestmentResearchEngine()
    
    elif provider == "claude":
        return InvestmentResearchEngine(ClaudeProvider(api_key=api_key))
    
    elif provider == "openai":
        return InvestmentResearchEngine(OpenAIProvider(api_key=api_key))
    
    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'auto', 'claude', or 'openai'")


# ============================================================================
# CLI for Testing
# ============================================================================

if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("Investment Thesis Lab - AI Research Module")
    print("=" * 60)
    
    try:
        engine = get_research_engine()
        print(f"✅ Provider: {engine.get_provider_name()}")
    except RuntimeError as e:
        print(f"❌ {e}")
        sys.exit(1)
    
    # Quick test
    if len(sys.argv) > 1:
        ticker = sys.argv[1].upper()
        print(f"\n🔍 Quick screening {ticker}...")
        result = engine.quick_screen(ticker)
        print(json.dumps(result, indent=2))

