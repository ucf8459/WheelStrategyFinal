"""
Newsletter Scanner Module
Scans Substack and other finance newsletters via RSS feeds
No API keys required - just pure RSS goodness!
"""

import os
import re
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import html
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import feedparser for RSS
try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False
    logger.warning("feedparser not installed - Newsletter scanning disabled. Run: pip install feedparser")

# Try to import BeautifulSoup for HTML parsing
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    logger.warning("beautifulsoup4 not installed - HTML parsing limited. Run: pip install beautifulsoup4")


# =============================================================================
# CURATED NEWSLETTER LIST
# =============================================================================

# High-quality finance/investment newsletters on Substack
CURATED_NEWSLETTERS = {
    # Macro & Markets
    'netinterest': {
        'name': 'Net Interest',
        'url': 'https://www.netinterest.co/feed',
        'author': 'Marc Rubinstein',
        'focus': 'Financial sector deep dives',
        'category': 'Finance'
    },
    'thediff': {
        'name': 'The Diff',
        'url': 'https://www.thediff.co/feed',
        'author': 'Byrne Hobart',
        'focus': 'Tech, finance, and strategy',
        'category': 'Tech/Finance'
    },
    'readmultiples': {
        'name': 'Multiples',
        'url': 'https://readmultiples.substack.com/feed',
        'author': 'Various',
        'focus': 'Valuation and investing',
        'category': 'Investing'
    },
    'thegeneralist': {
        'name': 'The Generalist',
        'url': 'https://www.generalist.com/feed',
        'author': 'Mario Gabriele',
        'focus': 'Tech company deep dives',
        'category': 'Tech'
    },
    'platformer': {
        'name': 'Platformer',
        'url': 'https://www.platformer.news/feed',
        'author': 'Casey Newton',
        'focus': 'Big tech news and analysis',
        'category': 'Tech'
    },
    'stockmarketmba': {
        'name': 'Stock Market MBA',
        'url': 'https://stockmarketmba.substack.com/feed',
        'author': 'Stock Market MBA',
        'focus': 'Fundamental analysis education',
        'category': 'Education'
    },
    'compoundingquality': {
        'name': 'Compounding Quality',
        'url': 'https://compoundingquality.substack.com/feed',
        'author': 'Compounding Quality',
        'focus': 'Quality investing',
        'category': 'Investing'
    },
    'marketsentiment': {
        'name': 'Market Sentiment',
        'url': 'https://marketsentiment.substack.com/feed',
        'author': 'Market Sentiment',
        'focus': 'Data-driven market analysis',
        'category': 'Data/Analysis'
    },
    'chartr': {
        'name': 'Chartr',
        'url': 'https://www.chartr.co/feed',
        'author': 'Chartr',
        'focus': 'Data visualization and trends',
        'category': 'Data/Trends'
    },
    'wheeldealings': {
        'name': 'Wheel Dealings',
        'url': 'https://wheeldealings.substack.com/feed',
        'author': 'Wheel Trader',
        'focus': 'Wheel strategy and options',
        'category': 'Options'
    },
}

# Common ticker patterns (same as social scanner)
TICKER_BLACKLIST = {
    'A', 'I', 'AM', 'PM', 'CEO', 'CFO', 'CTO', 'IPO', 'ETF', 'USA', 'GDP', 'CPI',
    'FBI', 'CIA', 'NASA', 'NYSE', 'SEC', 'FED', 'IMF', 'EU', 'UK', 'US', 'DD',
    'AI', 'ML', 'API', 'CEO', 'CFO', 'IPO', 'ETF', 'RSS', 'URL', 'PDF', 'HTML',
    'THE', 'AND', 'FOR', 'ARE', 'NOT', 'BUT', 'CAN', 'HAS', 'HAD', 'WAS', 'HIS',
    'HER', 'ONE', 'TWO', 'NOW', 'HOW', 'WHY', 'WHO', 'ANY', 'ALL', 'OUR', 'OUT',
    'NEW', 'OLD', 'TOP', 'BIG', 'LOW', 'HIGH', 'UP', 'DOWN', 'BUY', 'SELL',
    'READ', 'MORE', 'LESS', 'MOST', 'SOME', 'MANY', 'MUCH', 'VERY', 'JUST',
    'THIS', 'THAT', 'WHAT', 'WHEN', 'WITH', 'FROM', 'INTO', 'OVER', 'ALSO',
    'BEEN', 'HAVE', 'HERE', 'WILL', 'THEY', 'THEM', 'SAID', 'SAYS', 'WEEK',
    'YEAR', 'TODAY', 'THINK', 'KNOW', 'MAKE', 'TAKE', 'COME', 'WANT', 'LOOK',
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class NewsletterPost:
    """Represents a single newsletter post"""
    title: str
    link: str
    published: str
    author: str
    newsletter: str
    summary: str
    content_preview: str
    tickers_mentioned: List[str]
    word_count: int


@dataclass 
class Newsletter:
    """Represents a newsletter subscription"""
    id: str
    name: str
    url: str
    author: str
    focus: str
    category: str
    added_at: str
    last_fetched: Optional[str] = None
    post_count: int = 0


# =============================================================================
# NEWSLETTER SCANNER
# =============================================================================

class NewsletterScanner:
    """Scans finance newsletters via RSS feeds"""
    
    def __init__(self, config_path: str = None):
        """Initialize the scanner with optional custom config path"""
        self.config_path = config_path or os.path.join(
            os.path.dirname(__file__), 'newsletter_config.json'
        )
        self.newsletters: Dict[str, Newsletter] = {}
        self._load_config()
        
        if not FEEDPARSER_AVAILABLE:
            logger.warning("feedparser not available - install with: pip install feedparser")
    
    def _load_config(self):
        """Load newsletter configuration from file"""
        # Start with curated list
        for id, info in CURATED_NEWSLETTERS.items():
            self.newsletters[id] = Newsletter(
                id=id,
                name=info['name'],
                url=info['url'],
                author=info['author'],
                focus=info['focus'],
                category=info['category'],
                added_at=datetime.now().isoformat()
            )
        
        # Load any custom newsletters from config file
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    custom = json.load(f)
                    for id, info in custom.get('newsletters', {}).items():
                        self.newsletters[id] = Newsletter(**info)
                logger.info(f"Loaded {len(custom.get('newsletters', {}))} custom newsletters")
            except Exception as e:
                logger.error(f"Error loading newsletter config: {e}")
    
    def _save_config(self):
        """Save custom newsletter configuration"""
        try:
            # Only save non-curated newsletters
            custom = {
                'newsletters': {
                    id: asdict(nl) for id, nl in self.newsletters.items()
                    if id not in CURATED_NEWSLETTERS
                }
            }
            with open(self.config_path, 'w') as f:
                json.dump(custom, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving newsletter config: {e}")
    
    def add_newsletter(self, url: str, name: str = None) -> Dict:
        """Add a custom newsletter by URL"""
        # Normalize URL to RSS feed
        if 'substack.com' in url and '/feed' not in url:
            url = url.rstrip('/') + '/feed'
        
        # Generate ID from URL
        id = re.sub(r'[^a-z0-9]', '', url.lower())[:20]
        
        if id in self.newsletters:
            return {'error': 'Newsletter already exists', 'id': id}
        
        # Try to fetch and validate the feed
        if FEEDPARSER_AVAILABLE:
            try:
                feed = feedparser.parse(url)
                if feed.bozo and not feed.entries:
                    return {'error': f'Invalid RSS feed: {feed.bozo_exception}'}
                
                name = name or feed.feed.get('title', 'Unknown Newsletter')
                author = feed.feed.get('author', 'Unknown')
            except Exception as e:
                return {'error': f'Failed to fetch feed: {e}'}
        else:
            name = name or 'Custom Newsletter'
            author = 'Unknown'
        
        # Add the newsletter
        self.newsletters[id] = Newsletter(
            id=id,
            name=name,
            url=url,
            author=author,
            focus='Custom newsletter',
            category='Custom',
            added_at=datetime.now().isoformat()
        )
        
        self._save_config()
        
        return {
            'success': True,
            'id': id,
            'name': name,
            'message': f'Added newsletter: {name}'
        }
    
    def remove_newsletter(self, id: str) -> Dict:
        """Remove a newsletter"""
        if id in CURATED_NEWSLETTERS:
            return {'error': 'Cannot remove curated newsletters'}
        
        if id not in self.newsletters:
            return {'error': 'Newsletter not found'}
        
        name = self.newsletters[id].name
        del self.newsletters[id]
        self._save_config()
        
        return {'success': True, 'message': f'Removed newsletter: {name}'}
    
    def list_newsletters(self) -> List[Dict]:
        """List all configured newsletters"""
        return [
            {
                **asdict(nl),
                'is_curated': nl.id in CURATED_NEWSLETTERS
            }
            for nl in self.newsletters.values()
        ]
    
    def _extract_tickers(self, text: str) -> List[str]:
        """Extract potential stock tickers from text"""
        if not text:
            return []
        
        # Pattern: $TICKER or standalone TICKER (2-5 uppercase letters)
        dollar_tickers = re.findall(r'\$([A-Z]{1,5})\b', text.upper())
        standalone = re.findall(r'\b([A-Z]{2,5})\b', text)
        
        # Filter and deduplicate
        all_tickers = dollar_tickers + [t for t in standalone if t not in TICKER_BLACKLIST]
        
        seen = set()
        unique = []
        for t in all_tickers:
            if t not in seen and t not in TICKER_BLACKLIST:
                seen.add(t)
                unique.append(t)
        
        return unique[:10]  # Limit to top 10
    
    def _clean_html(self, html_content: str) -> str:
        """Strip HTML tags and clean up text"""
        if not html_content:
            return ''
        
        if BS4_AVAILABLE:
            soup = BeautifulSoup(html_content, 'html.parser')
            text = soup.get_text(separator=' ', strip=True)
        else:
            # Basic HTML stripping without BeautifulSoup
            text = re.sub(r'<[^>]+>', ' ', html_content)
            text = html.unescape(text)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def fetch_newsletter(self, newsletter_id: str, limit: int = 5) -> List[NewsletterPost]:
        """Fetch recent posts from a specific newsletter"""
        if not FEEDPARSER_AVAILABLE:
            return []
        
        if newsletter_id not in self.newsletters:
            logger.error(f"Newsletter not found: {newsletter_id}")
            return []
        
        nl = self.newsletters[newsletter_id]
        posts = []
        
        try:
            feed = feedparser.parse(nl.url)
            
            for entry in feed.entries[:limit]:
                # Get content
                content = ''
                if 'content' in entry:
                    content = entry.content[0].value if entry.content else ''
                elif 'summary' in entry:
                    content = entry.summary
                
                clean_content = self._clean_html(content)
                
                # Extract tickers from title and content
                tickers = self._extract_tickers(entry.title + ' ' + clean_content)
                
                posts.append(NewsletterPost(
                    title=entry.title,
                    link=entry.link,
                    published=entry.get('published', ''),
                    author=entry.get('author', nl.author),
                    newsletter=nl.name,
                    summary=entry.get('summary', '')[:300],
                    content_preview=clean_content[:500] + '...' if len(clean_content) > 500 else clean_content,
                    tickers_mentioned=tickers,
                    word_count=len(clean_content.split())
                ))
            
            # Update last fetched
            nl.last_fetched = datetime.now().isoformat()
            nl.post_count = len(feed.entries)
            
            logger.info(f"✅ Fetched {len(posts)} posts from {nl.name}")
            
        except Exception as e:
            logger.error(f"Error fetching {nl.name}: {e}")
        
        return posts
    
    def scan_all(self, posts_per_newsletter: int = 3) -> Dict:
        """Scan all newsletters and aggregate results"""
        if not FEEDPARSER_AVAILABLE:
            return {
                'error': 'feedparser not installed. Run: pip install feedparser',
                'posts': [],
                'tickers': {}
            }
        
        all_posts = []
        ticker_counts = {}
        ticker_sources = {}
        errors = []
        
        for nl_id in self.newsletters:
            try:
                posts = self.fetch_newsletter(nl_id, limit=posts_per_newsletter)
                all_posts.extend(posts)
                
                # Aggregate ticker mentions
                for post in posts:
                    for ticker in post.tickers_mentioned:
                        ticker_counts[ticker] = ticker_counts.get(ticker, 0) + 1
                        if ticker not in ticker_sources:
                            ticker_sources[ticker] = []
                        ticker_sources[ticker].append({
                            'newsletter': post.newsletter,
                            'title': post.title,
                            'link': post.link
                        })
                        
            except Exception as e:
                errors.append({'newsletter': nl_id, 'error': str(e)})
        
        # Sort posts by date (newest first)
        all_posts.sort(key=lambda x: x.published, reverse=True)
        
        # Sort tickers by mention count
        trending_tickers = [
            {
                'ticker': ticker,
                'mentions': count,
                'sources': ticker_sources.get(ticker, [])[:3]
            }
            for ticker, count in sorted(ticker_counts.items(), key=lambda x: -x[1])
        ][:15]
        
        return {
            'posts': [asdict(p) for p in all_posts],
            'total_posts': len(all_posts),
            'newsletters_scanned': len(self.newsletters),
            'trending_tickers': trending_tickers,
            'ticker_counts': ticker_counts,
            'errors': errors,
            'scanned_at': datetime.now().isoformat()
        }
    
    def get_posts_mentioning_ticker(self, ticker: str, limit: int = 10) -> List[Dict]:
        """Find posts that mention a specific ticker"""
        ticker = ticker.upper()
        matching_posts = []
        
        for nl_id in self.newsletters:
            posts = self.fetch_newsletter(nl_id, limit=5)
            for post in posts:
                if ticker in post.tickers_mentioned:
                    matching_posts.append(asdict(post))
        
        return matching_posts[:limit]


# =============================================================================
# MODULE INITIALIZATION
# =============================================================================

_scanner = None

def get_newsletter_scanner() -> NewsletterScanner:
    """Get or create the newsletter scanner singleton"""
    global _scanner
    if _scanner is None:
        _scanner = NewsletterScanner()
    return _scanner


def is_available() -> bool:
    """Check if newsletter scanning is available"""
    return FEEDPARSER_AVAILABLE


# Test on direct execution
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print(f"feedparser available: {FEEDPARSER_AVAILABLE}")
    print(f"beautifulsoup4 available: {BS4_AVAILABLE}")
    
    if FEEDPARSER_AVAILABLE:
        scanner = get_newsletter_scanner()
        print(f"\nConfigured newsletters: {len(scanner.newsletters)}")
        
        for nl in scanner.list_newsletters()[:5]:
            print(f"  - {nl['name']} ({nl['category']})")
        
        print("\nFetching sample posts...")
        results = scanner.scan_all(posts_per_newsletter=2)
        print(f"Total posts: {results['total_posts']}")
        print(f"Trending tickers: {[t['ticker'] for t in results['trending_tickers'][:5]]}")
