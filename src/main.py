from __future__ import annotations

import asyncio
from typing import Any

import httpx
from apify import Actor

from .extractor import DEFAULT_HEADERS, enrich_store, normalize_store_url


def _extract_input_domains(actor_input: dict[str, Any]) -> list[str]:
    """Support both 'domains' stringList and standard Apify 'startUrls' input formats."""
    raw_items: list[str] = []

    domains_field = actor_input.get("domains")
    if isinstance(domains_field, list):
        for item in domains_field:
            if isinstance(item, str) and item.strip():
                raw_items.append(item.strip())
            elif isinstance(item, dict) and isinstance(item.get("url"), str):
                raw_items.append(item["url"].strip())

    start_urls_field = actor_input.get("startUrls")
    if isinstance(start_urls_field, list):
        for item in start_urls_field:
            if isinstance(item, str) and item.strip():
                raw_items.append(item.strip())
            elif isinstance(item, dict) and isinstance(item.get("url"), str):
                raw_items.append(item["url"].strip())

    # Deduplicate by normalized domain while preserving order
    unique_targets: list[str] = []
    seen_domains: set[str] = set()
    for raw in raw_items:
        try:
            domain, _ = normalize_store_url(raw)
            if domain not in seen_domains:
                seen_domains.add(domain)
                unique_targets.append(raw)
        except ValueError:
            Actor.log.warning(f"Skipping invalid URL or domain input: {raw!r}")

    return unique_targets


async def main() -> None:
    """Main entrypoint for the Apify Actor."""
    async with Actor:
        actor_input = await Actor.get_input() or {}

        targets = _extract_input_domains(actor_input)
        if not targets:
            Actor.log.warning(
                "No valid domains provided in input. Using default sample store (allbirds.com)."
            )
            targets = ["https://www.allbirds.com"]

        max_contact_pages = int(actor_input.get("maxContactPages", 3))
        include_products_analytics = bool(actor_input.get("includeProductsAnalytics", True))
        only_shopify = bool(actor_input.get("onlyShopify", False))
        require_email = bool(actor_input.get("requireEmail", False))
        concurrency = max(1, min(int(actor_input.get("concurrency", 10)), 50))

        proxy_url: str | None = None
        proxy_config_input = actor_input.get("proxyConfiguration")
        if isinstance(proxy_config_input, dict) and proxy_config_input.get("useApifyProxy"):
            proxy_config = await Actor.create_proxy_configuration(
                actor_proxy_input=proxy_config_input
            )
            if proxy_config:
                proxy_url = await proxy_config.new_url()

        Actor.log.info(
            f"Starting Shopify Store Leads & Tech Stack enrichment for {len(targets)} store(s) "
            f"(concurrency={concurrency}, onlyShopify={only_shopify}, requireEmail={require_email})"
        )

        semaphore = asyncio.Semaphore(concurrency)
        saved_count = 0
        failed_count = 0

        async with httpx.AsyncClient(
            headers=DEFAULT_HEADERS,
            timeout=httpx.Timeout(20.0, connect=10.0),
            proxy=proxy_url,
            limits=httpx.Limits(max_connections=concurrency * 2, max_keepalive_connections=concurrency),
        ) as client:

            async def _process_one(target: str) -> None:
                nonlocal saved_count, failed_count
                async with semaphore:
                    try:
                        result = await enrich_store(
                            raw_domain=target,
                            client=client,
                            max_contact_pages=max_contact_pages,
                            include_products_analytics=include_products_analytics,
                        )

                        if only_shopify and not result.get("is_shopify"):
                            Actor.log.info(
                                f"[{result['domain']}] Skipped (not a Shopify store and onlyShopify=True)"
                            )
                            return

                        if require_email and not result.get("emails"):
                            Actor.log.info(
                                f"[{result['domain']}] Skipped (no emails found and requireEmail=True)"
                            )
                            return

                        await Actor.push_data(result)
                        saved_count += 1
                        Actor.log.info(
                            f"[{result['domain']}] Enriched -> Shopify={result['is_shopify']} | "
                            f"Emails={len(result['emails'])} | Apps={len(result['tech_stack'])} | "
                            f"Products={result['products_count_sampled']}"
                        )
                    except Exception as exc:
                        failed_count += 1
                        Actor.log.warning(f"Failed to enrich {target!r}: {type(exc).__name__}: {exc}")

            await asyncio.gather(*(_process_one(t) for t in targets))

        Actor.log.info(
            f"Finished enrichment! Saved {saved_count} store lead(s) to dataset ({failed_count} failed)."
        )
