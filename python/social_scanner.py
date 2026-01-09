"""
Social Media Scanner Module
Scans Reddit and StockTwits for investment sentiment and trending tickers
"""

import os
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import Counter
import json
import time

logger = logging.getLogger(__name__)

# Try to import PRAW for Reddit
try:
    import praw
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False
    logger.warning("PRAW not installed - Reddit scanning disabled. Run: pip install praw")

# Try to import requests for StockTwits
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


# =============================================================================
# CONFIGURATION
# =============================================================================

# Investment-focused subreddits
INVESTMENT_SUBREDDITS = [
    'thetagang',      # Wheel strategy experts - YOUR people!
    'wallstreetbets', # High conviction retail plays
    'stocks',         # General stock discussion
    'options',        # Options strategies
    'investing',      # Long-term investing
    'stockmarket',    # Market discussion
    'dividends',      # Dividend investing
]

# Common ticker patterns (exclude common words that look like tickers)
TICKER_BLACKLIST = {
    'A', 'I', 'AM', 'PM', 'CEO', 'CFO', 'CTO', 'IPO', 'ETF', 'USA', 'GDP', 'CPI',
    'FBI', 'CIA', 'NASA', 'NYSE', 'SEC', 'FED', 'IMF', 'EU', 'UK', 'US', 'DD',
    'YOLO', 'FOMO', 'HODL', 'ATH', 'ATL', 'OTM', 'ITM', 'ATM', 'DTE', 'IV', 'HV',
    'PE', 'EPS', 'ROI', 'ROE', 'PB', 'PS', 'EBITDA', 'FCF', 'DCF', 'TA', 'FA',
    'RED', 'GREEN', 'BLUE', 'ALL', 'NEW', 'OLD', 'TOP', 'BOT', 'THE', 'FOR',
    'ARE', 'NOT', 'BUT', 'CAN', 'HAS', 'HAD', 'WAS', 'ONE', 'TWO', 'NOW', 'HOW',
    'WHY', 'WHO', 'ANY', 'ALL', 'OUR', 'OUT', 'BIG', 'LOW', 'HIGH', 'UP', 'DOWN',
    'BUY', 'SELL', 'HOLD', 'LONG', 'SHORT', 'CALL', 'PUT', 'LEAP', 'CSP', 'CC',
    'EDIT', 'UPDATE', 'LINK', 'POST', 'HELP', 'NEED', 'WANT', 'LIKE', 'GOOD',
    'BAD', 'BEST', 'WORST', 'MOST', 'MORE', 'LESS', 'VERY', 'JUST', 'ONLY',
    'SOME', 'MANY', 'MUCH', 'SUCH', 'SAME', 'BOTH', 'EACH', 'THAN', 'THEN',
    'THIS', 'THAT', 'WHAT', 'WHEN', 'WITH', 'FROM', 'INTO', 'OVER', 'UNDER',
    'AGAIN', 'BEEN', 'HAVE', 'HERE', 'THERE', 'WHERE', 'WHICH', 'WHILE', 'WILL',
    'WOULD', 'COULD', 'SHOULD', 'THEY', 'THEM', 'THEIR', 'THESE', 'THOSE',
    'BEING', 'GOING', 'DOING', 'MAKE', 'MADE', 'TAKE', 'TOOK', 'COME', 'CAME',
    'SAID', 'SAYS', 'THINK', 'KNOW', 'KNEW', 'STILL', 'EVEN', 'BACK', 'WELL',
    'ALSO', 'JUST', 'ONLY', 'FIRST', 'LAST', 'NEXT', 'AFTER', 'BEFORE',
    'NEVER', 'EVER', 'ALWAYS', 'OFTEN', 'MAYBE', 'PROBABLY', 'ACTUALLY',
    'REALLY', 'TODAY', 'TOMORROW', 'YESTERDAY', 'WEEK', 'MONTH', 'YEAR',
    'PRICE', 'STOCK', 'SHARE', 'MARKET', 'TRADE', 'MONEY', 'CASH', 'PROFIT',
    'LOSS', 'GAIN', 'RISK', 'SAFE', 'VALUE', 'GROWTH', 'INCOME', 'YIELD',
    'ITM', 'OTM', 'ATM', 'IV', 'DELTA', 'THETA', 'GAMMA', 'VEGA', 'RHO',
    'OPEN', 'CLOSE', 'HIGH', 'LOW', 'BID', 'ASK', 'VOL', 'AVG', 'MAX', 'MIN',
    'LMAO', 'LMFAO', 'LOL', 'OMG', 'WTF', 'IMO', 'IMHO', 'TBH', 'BTW', 'FYI',
    'AMA', 'ELI5', 'TLDR', 'IIRC', 'TIL', 'PSA', 'OC', 'OP', 'TL', 'DR',
}

# Valid US stock exchanges for validation
VALID_EXCHANGES = ['NYSE', 'NASDAQ', 'AMEX']


# =============================================================================
# REDDIT SCANNER
# =============================================================================

class RedditScanner:
    """Scans Reddit for investment-related posts and extracts tickers/sentiment"""
    
    def __init__(self, client_id: str = None, client_secret: str = None, user_agent: str = None):
        """
        Initialize Reddit scanner with API credentials.
        Get credentials at: https://www.reddit.com/prefs/apps
        """
        self.reddit = None
        self.initialized = False
        
        if not PRAW_AVAILABLE:
            logger.warning("PRAW not available - Reddit scanning disabled")
            return
        
        # Try to get credentials from environment or parameters
        client_id = client_id or os.getenv('REDDIT_CLIENT_ID')
        client_secret = client_secret or os.getenv('REDDIT_CLIENT_SECRET')
        user_agent = user_agent or os.getenv('REDDIT_USER_AGENT', 'WheelStrategyScanner/1.0')
        
        if not client_id or not client_secret:
            logger.warning("Reddit credentials not configured. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in .env")
            return
        
        try:
            self.reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent
            )
            # Test connection
            self.reddit.user.me()
            self.initialized = True
            logger.info("✅ Reddit scanner initialized successfully")
        except Exception as e:
            logger.error(f"Reddit initialization failed: {e}")
            self.initialized = False
    
    def extract_tickers(self, text: str) -> List[str]:
        """Extract potential stock tickers from text"""
        if not text:
            return []
        
        # Pattern: $TICKER or standalone TICKER (1-5 uppercase letters)
        # Look for $TICKER format first (more reliable)
        dollar_tickers = re.findall(r'\$([A-Z]{1,5})\b', text.upper())
        
        # Look for standalone tickers (less reliable, needs more filtering)
        # Only match words that are 2-5 characters, all caps, not in blacklist
        words = re.findall(r'\b([A-Z]{2,5})\b', text.upper())
        standalone_tickers = [w for w in words if w not in TICKER_BLACKLIST]
        
        # Combine, prioritizing $TICKER mentions
        all_tickers = dollar_tickers + standalone_tickers
        
        # Return unique tickers, preserving order of first occurrence
        seen = set()
        unique = []
        for t in all_tickers:
            if t not in seen and t not in TICKER_BLACKLIST:
                seen.add(t)
                unique.append(t)
        
        return unique
    
    def analyze_sentiment_simple(self, text: str) -> Tuple[str, float]:
        """
        Simple rule-based sentiment analysis.
        Returns (sentiment, confidence) where sentiment is 'bullish', 'bearish', or 'neutral'
        """
        if not text:
            return 'neutral', 0.5
        
        text_lower = text.lower()
        
        # Bullish indicators
        bullish_words = [
            'buy', 'calls', 'long', 'moon', 'rocket', 'bull', 'bullish', 'pump',
            'undervalued', 'cheap', 'bargain', 'opportunity', 'upside', 'breakout',
            'strong', 'growth', 'profit', 'win', 'winning', 'squeeze', 'tendies',
            'diamond hands', 'hold', 'hodl', 'yolo', 'all in', 'load up', 'buying',
            'accumulate', 'accumulating', 'love', 'great', 'amazing', 'incredible',
            'explosive', 'parabolic', 'rip', 'soar', 'surge', 'rally', 'green',
            '🚀', '💎', '🙌', '📈', '🔥', '💰', '🤑', '✅',
        ]
        
        # Bearish indicators
        bearish_words = [
            'sell', 'puts', 'short', 'bear', 'bearish', 'dump', 'crash', 'tank',
            'overvalued', 'expensive', 'bubble', 'avoid', 'downside', 'breakdown',
            'weak', 'decline', 'loss', 'lose', 'losing', 'paper hands', 'exit',
            'selling', 'sold', 'hate', 'terrible', 'awful', 'disaster', 'scam',
            'fraud', 'garbage', 'trash', 'dead', 'dying', 'bankrupt', 'bankruptcy',
            'red', 'plunge', 'plummet', 'collapse', 'implode', 'baghold',
            '📉', '🐻', '💀', '☠️', '🗑️', '❌', '⚠️',
        ]
        
        bullish_count = sum(1 for word in bullish_words if word in text_lower)
        bearish_count = sum(1 for word in bearish_words if word in text_lower)
        
        total = bullish_count + bearish_count
        if total == 0:
            return 'neutral', 0.5
        
        bullish_ratio = bullish_count / total
        
        if bullish_ratio > 0.6:
            confidence = min(0.5 + (bullish_ratio - 0.5) * 0.8, 0.95)
            return 'bullish', confidence
        elif bullish_ratio < 0.4:
            confidence = min(0.5 + (0.5 - bullish_ratio) * 0.8, 0.95)
            return 'bearish', confidence
        else:
            return 'neutral', 0.5
    
    def scan_subreddit(self, subreddit_name: str, limit: int = 50, time_filter: str = 'day') -> List[Dict]:
        """
        Scan a subreddit for posts and extract ticker mentions with sentiment.
        
        Args:
            subreddit_name: Name of subreddit to scan
            limit: Number of posts to fetch
            time_filter: 'hour', 'day', 'week', 'month', 'year', 'all'
        
        Returns:
            List of post data with tickers and sentiment
        """
        if not self.initialized:
            return []
        
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            posts = []
            
            for post in subreddit.hot(limit=limit):
                # Combine title and selftext for analysis
                full_text = f"{post.title} {post.selftext}"
                tickers = self.extract_tickers(full_text)
                sentiment, confidence = self.analyze_sentiment_simple(full_text)
                
                if tickers:  # Only include posts that mention tickers
                    posts.append({
                        'subreddit': subreddit_name,
                        'title': post.title,
                        'url': f"https://reddit.com{post.permalink}",
                        'score': post.score,
                        'num_comments': post.num_comments,
                        'created_utc': datetime.fromtimestamp(post.created_utc).isoformat(),
                        'tickers': tickers,
                        'sentiment': sentiment,
                        'sentiment_confidence': confidence,
                        'flair': post.link_flair_text,
                        'author': str(post.author) if post.author else '[deleted]',
                    })
            
            logger.info(f"✅ Scanned r/{subreddit_name}: found {len(posts)} posts with ticker mentions")
            return posts
            
        except Exception as e:
            logger.error(f"Error scanning r/{subreddit_name}: {e}")
            return []
    
    def scan_all_subreddits(self, limit_per_sub: int = 25) -> Dict:
        """
        Scan all investment subreddits and aggregate results.
        
        Returns:
            {
                'posts': [...],
                'ticker_counts': {'NVDA': 15, 'AAPL': 12, ...},
                'ticker_sentiment': {'NVDA': {'bullish': 10, 'bearish': 3, 'neutral': 2}, ...},
                'trending': [{'ticker': 'NVDA', 'mentions': 15, 'sentiment': 'bullish', 'score': 0.77}, ...],
                'themes': [...],
                'scanned_at': '...'
            }
        """
        if not self.initialized:
            return {'error': 'Reddit not configured', 'posts': [], 'trending': []}
        
        all_posts = []
        ticker_counts = Counter()
        ticker_sentiment = {}
        ticker_scores = {}  # Track total upvotes per ticker
        
        for subreddit in INVESTMENT_SUBREDDITS:
            try:
                posts = self.scan_subreddit(subreddit, limit=limit_per_sub)
                all_posts.extend(posts)
                
                for post in posts:
                    for ticker in post['tickers']:
                        ticker_counts[ticker] += 1
                        
                        if ticker not in ticker_sentiment:
                            ticker_sentiment[ticker] = {'bullish': 0, 'bearish': 0, 'neutral': 0}
                        ticker_sentiment[ticker][post['sentiment']] += 1
                        
                        if ticker not in ticker_scores:
                            ticker_scores[ticker] = 0
                        ticker_scores[ticker] += post['score']
                
                time.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                logger.error(f"Error scanning r/{subreddit}: {e}")
                continue
        
        # Build trending list with sentiment scores
        trending = []
        for ticker, count in ticker_counts.most_common(30):
            sentiment_data = ticker_sentiment.get(ticker, {})
            total_mentions = sum(sentiment_data.values())
            
            if total_mentions > 0:
                bullish_pct = sentiment_data.get('bullish', 0) / total_mentions
                bearish_pct = sentiment_data.get('bearish', 0) / total_mentions
                
                if bullish_pct > 0.5:
                    overall_sentiment = 'bullish'
                    sentiment_score = bullish_pct
                elif bearish_pct > 0.5:
                    overall_sentiment = 'bearish'
                    sentiment_score = -bearish_pct
                else:
                    overall_sentiment = 'neutral'
                    sentiment_score = 0
            else:
                overall_sentiment = 'neutral'
                sentiment_score = 0
            
            trending.append({
                'ticker': ticker,
                'mentions': count,
                'sentiment': overall_sentiment,
                'sentiment_score': round(sentiment_score, 2),
                'bullish_pct': round(bullish_pct * 100, 1) if total_mentions > 0 else 0,
                'bearish_pct': round(bearish_pct * 100, 1) if total_mentions > 0 else 0,
                'total_score': ticker_scores.get(ticker, 0),
                'avg_score': round(ticker_scores.get(ticker, 0) / count, 1) if count > 0 else 0,
            })
        
        return {
            'posts': all_posts,
            'ticker_counts': dict(ticker_counts),
            'ticker_sentiment': ticker_sentiment,
            'trending': trending,
            'subreddits_scanned': INVESTMENT_SUBREDDITS,
            'total_posts': len(all_posts),
            'scanned_at': datetime.now().isoformat(),
        }
    
    def get_ticker_sentiment(self, ticker: str, limit: int = 100) -> Dict:
        """
        Search Reddit for mentions of a specific ticker and analyze sentiment.
        
        Args:
            ticker: Stock ticker to search for
            limit: Number of posts to analyze
        
        Returns:
            Detailed sentiment analysis for the ticker
        """
        if not self.initialized:
            return {'error': 'Reddit not configured'}
        
        try:
            posts = []
            
            # Search across all investment subreddits
            for subreddit_name in INVESTMENT_SUBREDDITS:
                try:
                    subreddit = self.reddit.subreddit(subreddit_name)
                    
                    # Search for ticker mentions
                    for post in subreddit.search(f"${ticker} OR {ticker}", limit=limit // len(INVESTMENT_SUBREDDITS), time_filter='week'):
                        full_text = f"{post.title} {post.selftext}"
                        
                        # Verify ticker is actually mentioned
                        if ticker.upper() in full_text.upper():
                            sentiment, confidence = self.analyze_sentiment_simple(full_text)
                            
                            posts.append({
                                'subreddit': subreddit_name,
                                'title': post.title,
                                'url': f"https://reddit.com{post.permalink}",
                                'score': post.score,
                                'num_comments': post.num_comments,
                                'created_utc': datetime.fromtimestamp(post.created_utc).isoformat(),
                                'sentiment': sentiment,
                                'sentiment_confidence': confidence,
                                'preview': post.selftext[:300] + '...' if len(post.selftext) > 300 else post.selftext,
                            })
                    
                    time.sleep(0.3)  # Rate limiting
                    
                except Exception as e:
                    logger.warning(f"Error searching r/{subreddit_name} for {ticker}: {e}")
                    continue
            
            # Aggregate sentiment
            sentiment_counts = {'bullish': 0, 'bearish': 0, 'neutral': 0}
            total_score = 0
            
            for post in posts:
                sentiment_counts[post['sentiment']] += 1
                total_score += post['score']
            
            total_posts = len(posts)
            
            if total_posts > 0:
                bullish_pct = sentiment_counts['bullish'] / total_posts
                bearish_pct = sentiment_counts['bearish'] / total_posts
                
                if bullish_pct > bearish_pct + 0.1:
                    overall = 'bullish'
                elif bearish_pct > bullish_pct + 0.1:
                    overall = 'bearish'
                else:
                    overall = 'neutral'
            else:
                bullish_pct = bearish_pct = 0
                overall = 'no_data'
            
            return {
                'ticker': ticker,
                'total_mentions': total_posts,
                'overall_sentiment': overall,
                'bullish_pct': round(bullish_pct * 100, 1),
                'bearish_pct': round(bearish_pct * 100, 1),
                'neutral_pct': round((1 - bullish_pct - bearish_pct) * 100, 1),
                'sentiment_counts': sentiment_counts,
                'total_upvotes': total_score,
                'avg_upvotes': round(total_score / total_posts, 1) if total_posts > 0 else 0,
                'posts': sorted(posts, key=lambda x: x['score'], reverse=True)[:20],  # Top 20 by score
                'subreddits_searched': INVESTMENT_SUBREDDITS,
                'searched_at': datetime.now().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Error getting sentiment for {ticker}: {e}")
            return {'error': str(e), 'ticker': ticker}


# =============================================================================
# STOCKTWITS SCANNER
# =============================================================================

class StockTwitsScanner:
    """Scans StockTwits for ticker sentiment (no auth required for basic access)"""
    
    BASE_URL = "https://api.stocktwits.com/api/2"
    
    def __init__(self):
        self.session = requests.Session() if REQUESTS_AVAILABLE else None
        if self.session:
            self.session.headers.update({
                'User-Agent': 'WheelStrategyScanner/1.0'
            })
    
    def get_ticker_sentiment(self, ticker: str) -> Dict:
        """
        Get sentiment data for a ticker from StockTwits.
        No authentication required for this endpoint.
        """
        if not self.session:
            return {'error': 'requests library not available'}
        
        try:
            url = f"{self.BASE_URL}/streams/symbol/{ticker}.json"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 404:
                return {'error': f'Ticker {ticker} not found on StockTwits'}
            
            response.raise_for_status()
            data = response.json()
            
            # Extract sentiment from messages
            messages = data.get('messages', [])
            sentiment_counts = {'bullish': 0, 'bearish': 0, 'neutral': 0}
            
            recent_posts = []
            for msg in messages[:30]:
                sentiment = msg.get('entities', {}).get('sentiment', {})
                if sentiment:
                    basic = sentiment.get('basic', '').lower()
                    if basic == 'bullish':
                        sentiment_counts['bullish'] += 1
                    elif basic == 'bearish':
                        sentiment_counts['bearish'] += 1
                    else:
                        sentiment_counts['neutral'] += 1
                else:
                    sentiment_counts['neutral'] += 1
                
                recent_posts.append({
                    'body': msg.get('body', ''),
                    'created_at': msg.get('created_at', ''),
                    'sentiment': sentiment.get('basic', 'neutral') if sentiment else 'neutral',
                    'user': msg.get('user', {}).get('username', 'unknown'),
                    'likes': msg.get('likes', {}).get('total', 0),
                })
            
            # Get symbol info
            symbol_info = data.get('symbol', {})
            
            total = sum(sentiment_counts.values())
            if total > 0:
                bullish_pct = sentiment_counts['bullish'] / total
                bearish_pct = sentiment_counts['bearish'] / total
                
                if bullish_pct > bearish_pct + 0.1:
                    overall = 'bullish'
                elif bearish_pct > bullish_pct + 0.1:
                    overall = 'bearish'
                else:
                    overall = 'neutral'
            else:
                bullish_pct = bearish_pct = 0
                overall = 'no_data'
            
            return {
                'ticker': ticker,
                'source': 'stocktwits',
                'total_messages': len(messages),
                'overall_sentiment': overall,
                'bullish_pct': round(bullish_pct * 100, 1),
                'bearish_pct': round(bearish_pct * 100, 1),
                'sentiment_counts': sentiment_counts,
                'watchers': symbol_info.get('watchlist_count', 0),
                'posts': recent_posts[:10],
                'fetched_at': datetime.now().isoformat(),
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"StockTwits API error for {ticker}: {e}")
            return {'error': str(e), 'ticker': ticker}
    
    def get_trending(self) -> Dict:
        """Get trending tickers from StockTwits"""
        if not self.session:
            return {'error': 'requests library not available'}
        
        try:
            url = f"{self.BASE_URL}/trending/symbols.json"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            trending = []
            for symbol in data.get('symbols', [])[:20]:
                trending.append({
                    'ticker': symbol.get('symbol', ''),
                    'title': symbol.get('title', ''),
                    'watchers': symbol.get('watchlist_count', 0),
                })
            
            return {
                'source': 'stocktwits',
                'trending': trending,
                'fetched_at': datetime.now().isoformat(),
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"StockTwits trending error: {e}")
            return {'error': str(e)}


# =============================================================================
# UNIFIED SOCIAL SCANNER
# =============================================================================

class SocialScanner:
    """Unified interface for all social media scanning"""
    
    def __init__(self):
        self.reddit = RedditScanner()
        self.stocktwits = StockTwitsScanner()
        logger.info("🔍 Social Scanner initialized")
    
    def scan_trending(self) -> Dict:
        """
        Scan all sources for trending tickers.
        Combines Reddit and StockTwits data.
        """
        results = {
            'reddit': None,
            'stocktwits': None,
            'combined_trending': [],
            'scanned_at': datetime.now().isoformat(),
        }
        
        # Scan Reddit
        if self.reddit.initialized:
            results['reddit'] = self.reddit.scan_all_subreddits(limit_per_sub=20)
        else:
            results['reddit'] = {'error': 'Reddit not configured', 'trending': []}
        
        # Get StockTwits trending
        results['stocktwits'] = self.stocktwits.get_trending()
        
        # Combine trending lists
        ticker_data = {}
        
        # Add Reddit data
        for item in results['reddit'].get('trending', []):
            ticker = item['ticker']
            ticker_data[ticker] = {
                'ticker': ticker,
                'reddit_mentions': item['mentions'],
                'reddit_sentiment': item['sentiment'],
                'reddit_bullish_pct': item.get('bullish_pct', 0),
                'stocktwits_watchers': 0,
                'combined_score': item['mentions'] * 2 + item.get('avg_score', 0) / 10,
            }
        
        # Add StockTwits data
        for item in results['stocktwits'].get('trending', []):
            ticker = item['ticker']
            if ticker in ticker_data:
                ticker_data[ticker]['stocktwits_watchers'] = item['watchers']
                ticker_data[ticker]['combined_score'] += item['watchers'] / 100
            else:
                ticker_data[ticker] = {
                    'ticker': ticker,
                    'reddit_mentions': 0,
                    'reddit_sentiment': 'unknown',
                    'reddit_bullish_pct': 0,
                    'stocktwits_watchers': item['watchers'],
                    'combined_score': item['watchers'] / 50,
                }
        
        # Sort by combined score
        results['combined_trending'] = sorted(
            ticker_data.values(),
            key=lambda x: x['combined_score'],
            reverse=True
        )[:25]
        
        return results
    
    def get_ticker_sentiment(self, ticker: str) -> Dict:
        """
        Get comprehensive sentiment for a ticker from all sources.
        """
        ticker = ticker.upper().strip()
        
        results = {
            'ticker': ticker,
            'reddit': None,
            'stocktwits': None,
            'overall_sentiment': 'neutral',
            'confidence': 0,
            'summary': '',
            'searched_at': datetime.now().isoformat(),
        }
        
        # Get Reddit sentiment
        if self.reddit.initialized:
            results['reddit'] = self.reddit.get_ticker_sentiment(ticker)
        else:
            results['reddit'] = {'error': 'Reddit not configured'}
        
        # Get StockTwits sentiment
        results['stocktwits'] = self.stocktwits.get_ticker_sentiment(ticker)
        
        # Calculate overall sentiment
        sentiments = []
        weights = []
        
        if results['reddit'] and not results['reddit'].get('error'):
            reddit_sent = results['reddit'].get('overall_sentiment', 'neutral')
            reddit_mentions = results['reddit'].get('total_mentions', 0)
            if reddit_sent in ['bullish', 'bearish', 'neutral'] and reddit_mentions > 0:
                sentiments.append(reddit_sent)
                weights.append(reddit_mentions)
        
        if results['stocktwits'] and not results['stocktwits'].get('error'):
            st_sent = results['stocktwits'].get('overall_sentiment', 'neutral')
            st_messages = results['stocktwits'].get('total_messages', 0)
            if st_sent in ['bullish', 'bearish', 'neutral'] and st_messages > 0:
                sentiments.append(st_sent)
                weights.append(st_messages)
        
        # Calculate weighted overall sentiment
        if sentiments:
            bullish_weight = sum(w for s, w in zip(sentiments, weights) if s == 'bullish')
            bearish_weight = sum(w for s, w in zip(sentiments, weights) if s == 'bearish')
            total_weight = sum(weights)
            
            if total_weight > 0:
                bullish_ratio = bullish_weight / total_weight
                bearish_ratio = bearish_weight / total_weight
                
                if bullish_ratio > 0.5:
                    results['overall_sentiment'] = 'bullish'
                    results['confidence'] = round(bullish_ratio, 2)
                elif bearish_ratio > 0.5:
                    results['overall_sentiment'] = 'bearish'
                    results['confidence'] = round(bearish_ratio, 2)
                else:
                    results['overall_sentiment'] = 'neutral'
                    results['confidence'] = 0.5
        
        # Generate summary
        reddit_data = results.get('reddit', {})
        st_data = results.get('stocktwits', {})
        
        reddit_mentions = reddit_data.get('total_mentions', 0) if not reddit_data.get('error') else 0
        st_messages = st_data.get('total_messages', 0) if not st_data.get('error') else 0
        
        results['summary'] = f"{ticker}: {results['overall_sentiment'].upper()} sentiment across {reddit_mentions} Reddit posts and {st_messages} StockTwits messages."
        
        return results
    
    def is_configured(self) -> Dict:
        """Check which services are configured and available"""
        return {
            'reddit': self.reddit.initialized,
            'stocktwits': REQUESTS_AVAILABLE,
            'message': 'Reddit requires REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in .env' if not self.reddit.initialized else 'All services configured',
        }


# =============================================================================
# MODULE INITIALIZATION
# =============================================================================

# Create singleton instance
social_scanner = None

def get_scanner() -> SocialScanner:
    """Get or create the social scanner singleton"""
    global social_scanner
    if social_scanner is None:
        social_scanner = SocialScanner()
    return social_scanner


# Test on direct execution
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    scanner = get_scanner()
    status = scanner.is_configured()
    print(f"Scanner status: {status}")
    
    if status['stocktwits']:
        print("\nTesting StockTwits...")
        st_result = scanner.stocktwits.get_ticker_sentiment('NVDA')
        print(f"NVDA StockTwits: {st_result.get('overall_sentiment')} ({st_result.get('bullish_pct')}% bullish)")
    
    if status['reddit']:
        print("\nTesting Reddit scan...")
        trending = scanner.scan_trending()
        print(f"Found {len(trending.get('combined_trending', []))} trending tickers")
        for t in trending.get('combined_trending', [])[:5]:
            print(f"  {t['ticker']}: {t['reddit_mentions']} Reddit mentions, {t['reddit_sentiment']}")
