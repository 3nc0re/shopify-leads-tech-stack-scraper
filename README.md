# Shopify Store Leads, Emails & Tech Stack Scraper

Extract **verified business emails, phone numbers, social media profiles, installed Shopify apps, ad pixels, and product catalog pricing analytics** from any list of Shopify stores — **fast, browserless, and at scale**.

Built for **B2B Lead Generation Agencies, Cold Emailers, Clay.com / n8n / Make workflows, UGC Agencies, and Shopify App Developers**.

---

## What data does this Shopify Scraper extract?

| Category | Extracted Fields |
| :--- | :--- |
| **Store Identity** | `domain`, `url`, `is_shopify`, `myshopify_domain` (`*.myshopify.com`), `store_name`, `description`, `theme_name`, `currency`, `country`, `language` |
| **Direct Contacts** | `emails` (auto-crawls homepage + `/pages/contact`, `/policies/contact-information`, legal pages), `phones` (`tel:` links & structured JSON-LD) |
| **Social Profiles** | `instagram`, `tiktok`, `facebook`, `youtube`, `linkedin`, `twitter` (X), `pinterest` |
| **Tech Stack & Pixels (35+)** | **Ads & Analytics:** Meta Pixel, TikTok Pixel, Google Tag Manager, GA4, Pinterest Tag, Snapchat Pixel, Microsoft Clarity, Hotjar, Triple Whale, Elevar<br>**Email & SMS:** Klaviyo, Omnisend, Mailchimp, Attentive, Postscript, Privy, Yotpo SMSBump, Drip, Brevo<br>**Reviews & Loyalty:** Judge.me, Loox, Yotpo, Okendo, Stamped.io, Trustpilot, Reviews.io, Smile.io, LoyaltyLion<br>**Support & Chat:** Gorgias, Zendesk, Tidio, Intercom, Re:amaze, Crisp, WhatsApp<br>**Subscriptions & BNPL:** Recharge, Skio, Loop, Bold, Shop Pay, Klarna, Afterpay, Affirm, Sezzle, PayPal |
| **Product & Price Analytics** | `products_count_sampled`, `avg_price`, `min_price`, `max_price`, `latest_product_date`, `vendors`, `product_types`, `sample_products` |

---

## Why use this Actor for B2B Lead Generation?

1. **Ultra-Fast & Lightweight (No Headless Browser):** Runs on pure asynchronous HTTP requests + `/products.json` inspection, meaning near-zero compute usage and blazing speed.
2. **Hyper-Targeted Cold Outreach Segmentation:**
   - *Email Marketing Agencies:* Filter stores running **Meta Pixel** or **TikTok Pixel** that **do NOT use Klaviyo** yet.
   - *UGC & Paid Social Agencies:* Find stores with **average product price > $50** and active Instagram/TikTok profiles.
   - *Customer Support SaaS:* Identify fast-growing brands using basic chat widgets instead of **Gorgias** or **Zendesk**.
   - *Active Store Verification:* Check `latest_product_date` and `products_count_sampled` to avoid outreach to dead or abandoned stores.
3. **Smart Noise Filtering:** Automatically strips out junk emails (`sentry.io`, `wixpress`, `.png`/`.webp` asset names, `noreply@`, placeholders).

---

## Input Example

You can pass simple domain names (`allbirds.com`) or full URLs (`https://www.allbirds.com`):

```json
{
  "domains": [
    "https://www.allbirds.com",
    "https://colourpop.com"
  ],
  "maxContactPages": 3,
  "includeProductsAnalytics": true,
  "onlyShopify": false,
  "requireEmail": false,
  "concurrency": 10
}
```

---

## Output Example

```json
{
  "domain": "colourpop.com",
  "url": "https://colourpop.com",
  "is_shopify": true,
  "myshopify_domain": "colourpop.myshopify.com",
  "store_name": "ColourPop",
  "description": "ColourPop Cosmetics - Cruelty-free makeup...",
  "currency": "USD",
  "country": "US",
  "language": "en",
  "theme_name": "ColourPop Custom",
  "emails": [
    "support@colourpop.com"
  ],
  "phones": [],
  "instagram": "https://www.instagram.com/colourpopcosmetics",
  "tiktok": "https://www.tiktok.com/@colourpopco",
  "facebook": "https://www.facebook.com/ColourPopCosmetics",
  "youtube": "https://www.youtube.com/@colourpopcosmetics",
  "linkedin": null,
  "twitter": "https://x.com/ColourPopCo",
  "pinterest": "https://www.pinterest.com/colourpopco",
  "tech_stack": [
    "Meta Pixel (Facebook)",
    "TikTok Pixel",
    "Google Tag Manager",
    "Klaviyo",
    "Yotpo",
    "Zendesk",
    "Shop Pay",
    "Afterpay / Clearpay",
    "PayPal"
  ],
  "tech_categories": {
    "ads_and_analytics": ["Meta Pixel (Facebook)", "TikTok Pixel", "Google Tag Manager"],
    "email_and_sms": ["Klaviyo"],
    "reviews_and_loyalty": ["Yotpo"],
    "support_and_chat": ["Zendesk"],
    "payments_and_bnpl": ["Shop Pay", "Afterpay / Clearpay", "PayPal"]
  },
  "products_count_sampled": 250,
  "avg_price": 18.45,
  "min_price": 5.0,
  "max_price": 89.0,
  "latest_product_date": "2026-10-20T09:00:00-07:00",
  "vendors": ["ColourPop"],
  "product_types": ["Eyeshadow", "Lipstick", "Face"],
  "sample_products": [
    {
      "title": "Shadow Palette",
      "price": 14.0,
      "vendor": "ColourPop",
      "product_type": "Eyeshadow",
      "url": "https://colourpop.com/products/shadow-palette",
      "image": "https://cdn.shopify.com/s/files/..."
    }
  ],
  "scraped_at": "2026-10-25T16:00:00+00:00"
}
```

---

## Integrations (Clay, n8n, Make, Zapier)

1. **Clay.com:** Use the native Apify integration in Clay, pass the company domain column into `domains`, and map `emails`, `tech_stack`, `avg_price`, and `instagram` directly into your Clay table for AI personalized email writing.
2. **n8n / Make:** Trigger this Actor via HTTP API (`https://api.apify.com/v2/acts/YOUR_USERNAME~shopify-leads-tech-stack-scraper/run-sync-get-dataset-items`) to enrich incoming leads in real time.
