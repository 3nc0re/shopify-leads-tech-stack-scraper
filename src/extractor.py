from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
}

EMAIL_REGEX = re.compile(
    r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,15}\b"
)

INVALID_EMAIL_EXTENSIONS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".avif",
    ".ico",
    ".css",
    ".js",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".mp4",
    ".mp3",
)

INVALID_EMAIL_DOMAINS = {
    "example.com",
    "domain.com",
    "yourdomain.com",
    "yoursite.com",
    "email.com",
    "test.com",
    "sample.com",
    "sentry.io",
    "ingest.sentry.io",
    "wixpress.com",
    "shopify.com",
    "myshopify.com",
    "schema.org",
    "w3.org",
}

INVALID_EMAIL_PREFIXES = (
    "noreply@",
    "no-reply@",
    "donotreply@",
    "do-not-reply@",
    "example@",
    "yourname@",
    "name@",
    "user@",
    "username@",
    "email@",
    "firstname@",
    "johndoe@",
)

SOCIAL_PATTERNS: dict[str, re.Pattern[str]] = {
    "instagram": re.compile(
        r"https?://(?:www\.)?instagram\.com/([a-zA-Z0-9_.\-]+)", re.IGNORECASE
    ),
    "tiktok": re.compile(
        r"https?://(?:www\.)?tiktok\.com/(@[a-zA-Z0-9_.\-]+)", re.IGNORECASE
    ),
    "facebook": re.compile(
        r"https?://(?:www\.)?(?:facebook|fb)\.com/([a-zA-Z0-9_.\-]+)", re.IGNORECASE
    ),
    "youtube": re.compile(
        r"https?://(?:www\.)?youtube\.com/(@[a-zA-Z0-9_.\-]+|(?:c|channel|user)/[a-zA-Z0-9_.\-]+)",
        re.IGNORECASE,
    ),
    "linkedin": re.compile(
        r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/(company/[a-zA-Z0-9_.\-]+|in/[a-zA-Z0-9_.\-]+)",
        re.IGNORECASE,
    ),
    "twitter": re.compile(
        r"https?://(?:www\.)?(?:twitter|x)\.com/([a-zA-Z0-9_]+)", re.IGNORECASE
    ),
    "pinterest": re.compile(
        r"https?://(?:[a-z]{2,3}\.)?pinterest\.(?:com|co\.uk|ca|de|fr)/([a-zA-Z0-9_.\-]+)",
        re.IGNORECASE,
    ),
}

IGNORED_SOCIAL_HANDLES = {
    "sharer",
    "sharer.php",
    "share",
    "intent",
    "home",
    "login",
    "signup",
    "explore",
    "p",
    "reel",
    "reels",
    "stories",
    "watch",
    "hashtag",
    "shopify",
    "pin",
    "dialog",
    "plugins",
    "tr",
}

TECH_SIGNATURES: dict[str, dict[str, list[str]]] = {
    "ads_and_analytics": {
        "Meta Pixel (Facebook)": ["connect.facebook.net", "fbq(", "facebook-jssdk"],
        "TikTok Pixel": ["analytics.tiktok.com", "ttq.load"],
        "Google Tag Manager": ["googletagmanager.com/gtm.js", "googletagmanager.com/ns.html"],
        "Google Analytics (GA4)": ["googletagmanager.com/gtag/js", "google-analytics.com"],
        "Pinterest Tag": ["s.pinimg.com/ct/core.js", "pintrk("],
        "Snapchat Pixel": ["sc-static.net/scevent.min.js", "snaptr("],
        "Microsoft Clarity": ["clarity.ms/tag/"],
        "Hotjar": ["static.hotjar.com"],
        "Triple Whale": ["triplewhale.com", "api.config-security.com"],
        "Elevar": ["getelevar.com"],
    },
    "email_and_sms": {
        "Klaviyo": ["static.klaviyo.com", "klaviyo.js", "_learnq"],
        "Omnisend": ["omnisnippet1.com", "omnisend.com"],
        "Mailchimp": ["chimpstatic.com", "list-manage.com"],
        "Attentive": ["attn.tv", "attentive.com"],
        "Postscript": ["sdk.postscript.io", "postscript.io"],
        "Privy": ["widget.privy.com", "privy.com"],
        "Yotpo SMSBump": ["smsbump.com"],
        "Drip": ["tag.getdrip.com"],
        "Brevo (Sendinblue)": ["sibautomation.com", "sendinblue.com"],
    },
    "reviews_and_loyalty": {
        "Judge.me": ["cdn.judge.me", "judgeme_"],
        "Loox": ["loox.io"],
        "Yotpo": ["staticw2.yotpo.com", "yotpo.com"],
        "Okendo": ["okendo.io"],
        "Stamped.io": ["stamped.io"],
        "Trustpilot": ["widget.trustpilot.com", "trustpilot.com"],
        "Reviews.io": ["widget.reviews.io"],
        "Smile.io": ["js.smile.io", "sweettooth.io"],
        "LoyaltyLion": ["sdk.loyaltylion.net"],
    },
    "support_and_chat": {
        "Gorgias": ["config.gorgias.chat", "gorgias.io"],
        "Zendesk": ["static.zdassets.com", "zendesk.com"],
        "Tidio": ["code.tidio.co"],
        "Intercom": ["widget.intercom.io"],
        "Re:amaze": ["reamaze.js", "reamaze.com"],
        "Crisp": ["client.crisp.chat"],
        "WhatsApp Chat": ["wa.me/", "api.whatsapp.com/send"],
    },
    "subscriptions_and_upsell": {
        "Recharge": ["rechargeassets.com", "rechargepayments.com"],
        "Skio": ["skio.com"],
        "Loop Subscriptions": ["loopwork.co"],
        "Bold Subscriptions": ["boldapps.net"],
        "ReConvert": ["reconvert.io"],
    },
    "payments_and_bnpl": {
        "Shop Pay": ["shopify-payment-button", "shop.app/pay", "shopify_pay"],
        "Klarna": ["klarna.com", "klarnaservices.com"],
        "Afterpay / Clearpay": ["afterpay.com", "clearpay.co.uk", "portal.afterpay.com"],
        "Affirm": ["cdn1.affirm.com", "affirm.com"],
        "Sezzle": ["widget.sezzle.com"],
        "PayPal": ["paypal.com/sdk/js", "paypalobjects.com"],
    },
}

CONTACT_PATH_KEYWORDS = (
    "contact",
    "about",
    "impressum",
    "legal",
    "support",
    "help",
    "customer-service",
    "customer-care",
    "policies/contact-information",
    "policies/privacy-policy",
    "policies/terms-of-service",
)

FALLBACK_CONTACT_PATHS = (
    "/pages/contact",
    "/pages/contact-us",
    "/policies/contact-information",
    "/pages/about",
    "/pages/about-us",
)


def normalize_store_url(raw_input: str) -> tuple[str, str]:
    """Normalize a raw domain or URL into (domain, base_url)."""
    cleaned = raw_input.strip()
    if not cleaned:
        raise ValueError("Empty domain or URL provided")

    if not cleaned.startswith(("http://", "https://")):
        cleaned = f"https://{cleaned}"

    parsed = urlparse(cleaned)
    netloc = parsed.netloc.lower()
    if not netloc:
        raise ValueError(f"Invalid URL or domain: {raw_input}")

    domain = netloc[4:] if netloc.startswith("www.") else netloc
    base_url = f"https://{netloc}"
    return domain, base_url


def is_valid_email(email: str) -> bool:
    """Validate extracted email and filter out false positives like image files or placeholders."""
    cleaned = unquote(email).strip().lower().strip(".,;:'\"()[]{}<>")
    if not cleaned or "@" not in cleaned or len(cleaned) > 120:
        return False

    if any(cleaned.endswith(ext) for ext in INVALID_EMAIL_EXTENSIONS):
        return False

    if any(cleaned.startswith(prefix) for prefix in INVALID_EMAIL_PREFIXES):
        return False

    local_part, _, domain_part = cleaned.partition("@")
    if not local_part or not domain_part or "." not in domain_part:
        return False

    if domain_part in INVALID_EMAIL_DOMAINS:
        return False

    if any(domain_part.endswith(f".{bad}") for bad in INVALID_EMAIL_DOMAINS):
        return False

    # Filter out hex hashes (e.g. Sentry keys like 8f3a9b1c2d@...)
    if len(local_part) >= 24 and all(c in "0123456789abcdef" for c in local_part):
        return False

    # Filter version strings like react@18.2.0
    if re.match(r"^\d+\.\d+", domain_part):
        return False

    return bool(EMAIL_REGEX.fullmatch(cleaned))


def clean_email(email: str) -> str:
    """Return lowercase normalized email."""
    return unquote(email).strip().lower().strip(".,;:'\"()[]{}<>")


def extract_emails_from_html(html: str, soup: BeautifulSoup | None = None) -> list[str]:
    """Extract unique valid emails from mailto links, JSON-LD, and text/HTML content."""
    if soup is None:
        soup = BeautifulSoup(html, "lxml")

    found: list[str] = []
    seen: set[str] = set()

    def _add(candidate: str) -> None:
        cleaned = clean_email(candidate)
        if cleaned not in seen and is_valid_email(cleaned):
            seen.add(cleaned)
            found.append(cleaned)

    # 1. High-confidence mailto: links
    for a_tag in soup.select('a[href^="mailto:"]'):
        href = str(a_tag.get("href", ""))
        mailto_target = href[7:].split("?")[0]
        _add(mailto_target)

    # 2. Visible text & raw HTML regex
    text_content = soup.get_text(" ", strip=True)
    for match in EMAIL_REGEX.findall(text_content):
        _add(match)

    for match in EMAIL_REGEX.findall(html):
        _add(match)

    return found


def extract_phones_from_html(html: str, soup: BeautifulSoup | None = None) -> list[str]:
    """Extract phone numbers reliably from tel: links and structured JSON-LD data."""
    if soup is None:
        soup = BeautifulSoup(html, "lxml")

    phones: list[str] = []
    seen_digits: set[str] = set()

    def _add_phone(raw_phone: str) -> None:
        cleaned = unquote(raw_phone).strip()
        cleaned = re.sub(r"^(tel:|phone:)\s*", "", cleaned, flags=re.IGNORECASE).strip()
        digits = re.sub(r"\D", "", cleaned)
        if 7 <= len(digits) <= 15 and digits not in seen_digits:
            seen_digits.add(digits)
            phones.append(cleaned)

    # 1. tel: links
    for a_tag in soup.select('a[href^="tel:"]'):
        href = str(a_tag.get("href", ""))
        _add_phone(href)

    # 2. JSON-LD telephone fields
    for script in soup.find_all("script", type="application/ld+json"):
        raw_json = script.string or ""
        if not raw_json.strip():
            continue
        try:
            data = json.loads(raw_json)
            _extract_jsonld_phones(data, _add_phone)
        except Exception:
            continue

    return phones


def _extract_jsonld_phones(data: Any, callback: Any) -> None:
    if isinstance(data, dict):
        for key, value in data.items():
            if key.lower() == "telephone" and isinstance(value, str):
                callback(value)
            else:
                _extract_jsonld_phones(value, callback)
    elif isinstance(data, list):
        for item in data:
            _extract_jsonld_phones(item, callback)


def extract_socials_from_html(html: str) -> dict[str, str | None]:
    """Extract primary social media profile URLs from HTML."""
    socials: dict[str, str | None] = {
        "instagram": None,
        "tiktok": None,
        "facebook": None,
        "youtube": None,
        "linkedin": None,
        "twitter": None,
        "pinterest": None,
    }

    for platform, pattern in SOCIAL_PATTERNS.items():
        for match in pattern.finditer(html):
            handle = match.group(1).strip("/")
            handle_lower = handle.lower().split("/")[0]
            if not handle_lower or handle_lower in IGNORED_SOCIAL_HANDLES:
                continue

            if platform == "twitter":
                socials[platform] = f"https://x.com/{handle}"
            elif platform == "facebook":
                socials[platform] = f"https://www.facebook.com/{handle}"
            elif platform == "instagram":
                socials[platform] = f"https://www.instagram.com/{handle}"
            elif platform == "tiktok":
                socials[platform] = f"https://www.tiktok.com/{handle}"
            elif platform == "youtube":
                socials[platform] = f"https://www.youtube.com/{handle}"
            elif platform == "linkedin":
                socials[platform] = f"https://www.linkedin.com/{handle}"
            elif platform == "pinterest":
                socials[platform] = f"https://www.pinterest.com/{handle}"
            break

    return socials


def detect_tech_stack(html: str) -> tuple[list[str], dict[str, list[str]]]:
    """Detect installed Shopify apps, marketing pixels, and payment providers."""
    html_lower = html.lower()
    all_detected: list[str] = []
    by_category: dict[str, list[str]] = {}

    for category, tools in TECH_SIGNATURES.items():
        category_hits: list[str] = []
        for tool_name, signatures in tools.items():
            if any(sig.lower() in html_lower for sig in signatures):
                all_detected.append(tool_name)
                category_hits.append(tool_name)
        if category_hits:
            by_category[category] = category_hits

    return all_detected, by_category


def parse_shopify_metadata(html: str, soup: BeautifulSoup | None = None) -> dict[str, Any]:
    """Extract Shopify store metadata (Shopify.shop, theme, currency, country, title, description)."""
    if soup is None:
        soup = BeautifulSoup(html, "lxml")

    is_shopify = any(
        marker in html
        for marker in (
            "Shopify.shop",
            "cdn.shopify.com",
            "shopify-digital-wallet",
            "Shopify.theme",
            "/checkouts/internal/",
        )
    )

    myshopify_match = re.search(
        r'Shopify\.shop\s*=\s*["\']([a-zA-Z0-9\-]+\.myshopify\.com)["\']', html
    )
    myshopify_domain = myshopify_match.group(1) if myshopify_match else None
    if myshopify_domain:
        is_shopify = True

    theme_name: str | None = None
    theme_match = re.search(r"Shopify\.theme\s*=\s*(\{[^;]+\})", html)
    if theme_match:
        try:
            theme_obj = json.loads(theme_match.group(1))
            theme_name = theme_obj.get("name")
        except Exception:
            name_fallback = re.search(r'"name"\s*:\s*"([^"]+)"', theme_match.group(1))
            if name_fallback:
                theme_name = name_fallback.group(1)

    currency_match = re.search(
        r'Shopify\.currency\s*=\s*\{"active"\s*:\s*"([A-Z]{3})"', html
    )
    currency = currency_match.group(1) if currency_match else None
    if not currency:
        meta_curr = soup.find("meta", attrs={"property": "og:price:currency"})
        if meta_curr and meta_curr.get("content"):
            currency = str(meta_curr["content"]).strip().upper()

    country_match = re.search(r'Shopify\.country\s*=\s*["\']([A-Z]{2})["\']', html)
    country = country_match.group(1) if country_match else None

    html_tag = soup.find("html")
    language = str(html_tag.get("lang")).strip() if html_tag and html_tag.get("lang") else None

    store_name: str | None = None
    og_site_name = soup.find("meta", attrs={"property": "og:site_name"})
    if og_site_name and og_site_name.get("content"):
        store_name = str(og_site_name["content"]).strip()
    elif soup.title and soup.title.string:
        raw_title = soup.title.string.strip()
        store_name = re.split(r"\s*[\|–—\-]\s*", raw_title)[0].strip()

    description: str | None = None
    meta_desc = soup.find("meta", attrs={"name": "description"}) or soup.find(
        "meta", attrs={"property": "og:description"}
    )
    if meta_desc and meta_desc.get("content"):
        description = str(meta_desc["content"]).strip()

    return {
        "is_shopify": is_shopify,
        "myshopify_domain": myshopify_domain,
        "store_name": store_name,
        "description": description,
        "currency": currency,
        "country": country,
        "language": language,
        "theme_name": theme_name,
    }


def discover_contact_urls(base_url: str, soup: BeautifulSoup, max_pages: int = 3) -> list[str]:
    """Find internal links to Contact, About, or Legal pages."""
    if max_pages <= 0:
        return []

    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc.lower().removeprefix("www.")

    candidates: list[str] = []
    seen: set[str] = {base_url.rstrip("/")}

    for a_tag in soup.find_all("a", href=True):
        href = str(a_tag["href"]).strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        full_url = urljoin(base_url, href).split("#")[0].rstrip("/")
        parsed = urlparse(full_url)
        link_domain = parsed.netloc.lower().removeprefix("www.")
        if link_domain != base_domain:
            continue

        path_lower = parsed.path.lower()
        if any(keyword in path_lower for keyword in CONTACT_PATH_KEYWORDS):
            if full_url not in seen:
                seen.add(full_url)
                candidates.append(full_url)

    # Prioritize links containing 'contact' first
    candidates.sort(key=lambda u: (0 if "contact" in u.lower() else 1, len(u)))

    # Add standard Shopify fallback contact paths if we still have room
    for fallback_path in FALLBACK_CONTACT_PATHS:
        if len(candidates) >= max_pages:
            break
        fallback_url = f"{base_url.rstrip('/')}{fallback_path}"
        if fallback_url not in seen:
            seen.add(fallback_url)
            candidates.append(fallback_url)

    return candidates[:max_pages]


def parse_products_json(payload: dict[str, Any], base_url: str) -> dict[str, Any]:
    """Analyze Shopify /products.json payload for pricing, recency, and vendor intelligence."""
    products = payload.get("products")
    if not isinstance(products, list) or not products:
        return {
            "products_count_sampled": 0,
            "avg_price": None,
            "min_price": None,
            "max_price": None,
            "latest_product_date": None,
            "vendors": [],
            "product_types": [],
            "sample_products": [],
        }

    prices: list[float] = []
    vendors: set[str] = set()
    product_types: set[str] = set()
    published_dates: list[str] = []
    sample_products: list[dict[str, Any]] = []

    for product in products:
        if not isinstance(product, dict):
            continue

        vendor = str(product.get("vendor") or "").strip()
        if vendor:
            vendors.add(vendor)

        p_type = str(product.get("product_type") or "").strip()
        if p_type:
            product_types.append(p_type) if isinstance(product_types, list) else product_types.add(p_type)

        pub_at = str(product.get("published_at") or product.get("created_at") or "").strip()
        if pub_at:
            published_dates.append(pub_at)

        variants = product.get("variants")
        product_price: float | None = None
        if isinstance(variants, list):
            for variant in variants:
                if not isinstance(variant, dict):
                    continue
                raw_price = variant.get("price")
                try:
                    val = float(raw_price)
                    if val > 0:
                        prices.append(val)
                        if product_price is None:
                            product_price = val
                except (TypeError, ValueError):
                    continue

        if len(sample_products) < 5:
            handle = product.get("handle")
            images = product.get("images")
            image_url = (
                images[0].get("src")
                if isinstance(images, list) and images and isinstance(images[0], dict)
                else None
            )
            sample_products.append(
                {
                    "title": product.get("title"),
                    "price": product_price,
                    "vendor": vendor or None,
                    "product_type": p_type or None,
                    "url": f"{base_url.rstrip('/')}/products/{handle}" if handle else None,
                    "image": image_url,
                }
            )

    avg_price = round(sum(prices) / len(prices), 2) if prices else None
    min_price = round(min(prices), 2) if prices else None
    max_price = round(max(prices), 2) if prices else None
    latest_date = max(published_dates) if published_dates else None

    return {
        "products_count_sampled": len(products),
        "avg_price": avg_price,
        "min_price": min_price,
        "max_price": max_price,
        "latest_product_date": latest_date,
        "vendors": sorted(vendors)[:20],
        "product_types": sorted(product_types)[:20],
        "sample_products": sample_products,
    }


async def enrich_store(
    raw_domain: str,
    client: httpx.AsyncClient,
    max_contact_pages: int = 3,
    include_products_analytics: bool = True,
) -> dict[str, Any]:
    """Perform full B2B enrichment on a single store domain."""
    domain, base_url = normalize_store_url(raw_domain)

    home_resp = await client.get(base_url, follow_redirects=True)
    home_resp.raise_for_status()
    final_base_url = f"{home_resp.url.scheme}://{home_resp.url.netloc}"
    home_html = home_resp.text
    home_soup = BeautifulSoup(home_html, "lxml")

    metadata = parse_shopify_metadata(home_html, home_soup)
    emails = extract_emails_from_html(home_html, home_soup)
    phones = extract_phones_from_html(home_html, home_soup)
    socials = extract_socials_from_html(home_html)
    tech_stack, tech_categories = detect_tech_stack(home_html)

    # Crawl internal contact/policy pages to maximize email & phone discovery
    contact_urls = discover_contact_urls(final_base_url, home_soup, max_pages=max_contact_pages)
    seen_emails = set(emails)
    seen_phones = set(phones)

    for contact_url in contact_urls:
        try:
            sub_resp = await client.get(contact_url, follow_redirects=True)
            if sub_resp.status_code != 200:
                continue
            sub_html = sub_resp.text
            sub_soup = BeautifulSoup(sub_html, "lxml")

            for em in extract_emails_from_html(sub_html, sub_soup):
                if em not in seen_emails:
                    seen_emails.add(em)
                    emails.append(em)

            for ph in extract_phones_from_html(sub_html, sub_soup):
                if ph not in seen_phones:
                    seen_phones.add(ph)
                    phones.append(ph)

            sub_socials = extract_socials_from_html(sub_html)
            for platform, link in sub_socials.items():
                if not socials.get(platform) and link:
                    socials[platform] = link
        except Exception:
            continue

    # Fetch /products.json for catalog & pricing intelligence
    catalog_stats: dict[str, Any] = {
        "products_count_sampled": 0,
        "avg_price": None,
        "min_price": None,
        "max_price": None,
        "latest_product_date": None,
        "vendors": [],
        "product_types": [],
        "sample_products": [],
    }

    if include_products_analytics:
        products_url = f"{final_base_url}/products.json?limit=250"
        try:
            prod_resp = await client.get(products_url, follow_redirects=True)
            if prod_resp.status_code == 200 and "products" in prod_resp.text:
                payload = prod_resp.json()
                if isinstance(payload, dict) and isinstance(payload.get("products"), list):
                    metadata["is_shopify"] = True
                    catalog_stats = parse_products_json(payload, final_base_url)
        except Exception:
            pass

    return {
        "domain": domain,
        "url": final_base_url,
        **metadata,
        "emails": emails,
        "phones": phones,
        **socials,
        "tech_stack": tech_stack,
        "tech_categories": tech_categories,
        **catalog_stats,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }
