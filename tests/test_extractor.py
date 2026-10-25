from __future__ import annotations

import httpx
import pytest
from bs4 import BeautifulSoup

from src.extractor import (
    detect_tech_stack,
    discover_contact_urls,
    enrich_store,
    extract_emails_from_html,
    extract_phones_from_html,
    extract_socials_from_html,
    is_valid_email,
    normalize_store_url,
    parse_products_json,
    parse_shopify_metadata,
)


def test_normalize_store_url() -> None:
    domain, base_url = normalize_store_url("www.Allbirds.com/collections/mens")
    assert domain == "allbirds.com"
    assert base_url == "https://www.allbirds.com"

    domain2, base_url2 = normalize_store_url("https://gymshark.com")
    assert domain2 == "gymshark.com"
    assert base_url2 == "https://gymshark.com"


def test_is_valid_email_filtering() -> None:
    assert is_valid_email("hello@brandstore.com") is True
    assert is_valid_email("support@my-shop.co.uk") is True

    # False positives that must be rejected
    assert is_valid_email("banner@2x.png") is False
    assert is_valid_email("logo@3x.webp") is False
    assert is_valid_email("noreply@brandstore.com") is False
    assert is_valid_email("user@example.com") is False
    assert is_valid_email("8f3a9b1c2d3e4f5a6b7c8d9e0f1a2b3c@sentry.io") is False
    assert is_valid_email("react@18.2.0") is False


def test_extract_emails_and_phones_from_html() -> None:
    sample_html = """
    <html>
      <head>
        <script type="application/ld+json">
          {"@context": "https://schema.org", "@type": "Organization", "telephone": "+1 (800) 555-0199"}
        </script>
      </head>
      <body>
        <a href="mailto:sales@glowcosmetics.com?subject=Inquiry">Email Us</a>
        <a href="tel:+442079460921">Call UK</a>
        <p>For press inquiries contact press@glowcosmetics.com or support@example.com</p>
        <img src="hero@2x.png" />
      </body>
    </html>
    """
    soup = BeautifulSoup(sample_html, "lxml")
    emails = extract_emails_from_html(sample_html, soup)
    phones = extract_phones_from_html(sample_html, soup)

    assert emails == ["sales@glowcosmetics.com", "press@glowcosmetics.com"]
    assert "+442079460921" in phones
    assert "+1 (800) 555-0199" in phones


def test_extract_socials_and_tech_stack() -> None:
    sample_html = """
    <html>
      <head>
        <script src="https://static.klaviyo.com/onsite/js/klaviyo.js?company_id=ABC"></script>
        <script src="https://connect.facebook.net/en_US/fbevents.js"></script>
        <script src="https://config.gorgias.chat/gorgias-chat-bundle.js"></script>
        <script src="https://cdn.judge.me/widget_preloader.js"></script>
      </head>
      <body>
        <a href="https://www.instagram.com/sharer.php">Share</a>
        <a href="https://www.instagram.com/glowcosmetics/">Instagram</a>
        <a href="https://www.tiktok.com/@glowcosmetics">TikTok</a>
        <a href="https://twitter.com/intent/tweet">Tweet</a>
        <a href="https://x.com/glowbrand">X</a>
      </body>
    </html>
    """
    socials = extract_socials_from_html(sample_html)
    assert socials["instagram"] == "https://www.instagram.com/glowcosmetics"
    assert socials["tiktok"] == "https://www.tiktok.com/@glowcosmetics"
    assert socials["twitter"] == "https://x.com/glowbrand"

    tech_stack, categories = detect_tech_stack(sample_html)
    assert "Klaviyo" in tech_stack
    assert "Meta Pixel (Facebook)" in tech_stack
    assert "Gorgias" in tech_stack
    assert "Judge.me" in tech_stack
    assert categories["email_and_sms"] == ["Klaviyo"]


def test_parse_shopify_metadata_and_products() -> None:
    sample_html = """
    <html lang="en">
      <head>
        <title>Glow Cosmetics | Official Store</title>
        <meta name="description" content="Vegan skincare products." />
        <script>
          Shopify.shop = "glow-cosmetics-store.myshopify.com";
          Shopify.currency = {"active":"USD","rate":"1.0"};
          Shopify.country = "US";
          Shopify.theme = {"name":"Dawn","id":12345};
        </script>
      </head>
      <body>
        <a href="/pages/contact-us">Contact</a>
      </body>
    </html>
    """
    soup = BeautifulSoup(sample_html, "lxml")
    meta = parse_shopify_metadata(sample_html, soup)
    assert meta["is_shopify"] is True
    assert meta["myshopify_domain"] == "glow-cosmetics-store.myshopify.com"
    assert meta["currency"] == "USD"
    assert meta["country"] == "US"
    assert meta["theme_name"] == "Dawn"
    assert meta["store_name"] == "Glow Cosmetics"

    contact_links = discover_contact_urls("https://glowcosmetics.com", soup, max_pages=2)
    assert contact_links[0] == "https://glowcosmetics.com/pages/contact-us"

    products_payload = {
        "products": [
            {
                "title": "Vitamin C Serum",
                "handle": "vitamin-c-serum",
                "vendor": "GlowLab",
                "product_type": "Skincare",
                "published_at": "2026-10-01T12:00:00Z",
                "variants": [{"price": "30.00"}, {"price": "50.00"}],
                "images": [{"src": "https://cdn.shopify.com/serum.jpg"}],
            },
            {
                "title": "Hydrating Cleanser",
                "handle": "hydrating-cleanser",
                "vendor": "GlowLab",
                "product_type": "Cleanser",
                "published_at": "2026-10-15T12:00:00Z",
                "variants": [{"price": "10.00"}],
                "images": [],
            },
        ]
    }
    stats = parse_products_json(products_payload, "https://glowcosmetics.com")
    assert stats["products_count_sampled"] == 2
    assert stats["min_price"] == 10.0
    assert stats["max_price"] == 50.0
    assert stats["avg_price"] == 30.0
    assert stats["latest_product_date"] == "2026-10-15T12:00:00Z"
    assert stats["vendors"] == ["GlowLab"]


@pytest.mark.asyncio
async def test_enrich_store_with_mock_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(
                200,
                text="""
                <html lang="en">
                <head>
                    <title>TestBrand - Best Gear</title>
                    <script>Shopify.shop = "testbrand.myshopify.com"; Shopify.currency = {"active":"EUR"};</script>
                    <script src="https://static.klaviyo.com/onsite/js/klaviyo.js"></script>
                </head>
                <body>
                    <a href="/pages/contact">Contact Us</a>
                    <a href="https://www.instagram.com/testbrand">IG</a>
                </body>
                </html>
                """,
            )
        if request.url.path == "/pages/contact":
            return httpx.Response(
                200,
                text='<html><body>Reach us at <a href="mailto:hello@testbrand.eu">hello@testbrand.eu</a></body></html>',
            )
        if request.url.path == "/products.json":
            return httpx.Response(
                200,
                json={
                    "products": [
                        {
                            "title": "Pro Backpack",
                            "handle": "pro-backpack",
                            "vendor": "TestBrand",
                            "product_type": "Bags",
                            "published_at": "2026-09-10T10:00:00Z",
                            "variants": [{"price": "99.50"}],
                        }
                    ]
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await enrich_store("testbrand.eu", client, max_contact_pages=2)

    assert result["domain"] == "testbrand.eu"
    assert result["is_shopify"] is True
    assert result["myshopify_domain"] == "testbrand.myshopify.com"
    assert result["currency"] == "EUR"
    assert result["emails"] == ["hello@testbrand.eu"]
    assert result["instagram"] == "https://www.instagram.com/testbrand"
    assert "Klaviyo" in result["tech_stack"]
    assert result["products_count_sampled"] == 1
    assert result["avg_price"] == 99.5
