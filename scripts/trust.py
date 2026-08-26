#!/usr/bin/env python3
"""Deterministic editorial verification and corrections contract."""

from urllib.parse import urlparse

VERIFIED_AUTHORITY = 'OWNER_APPROVED_AUTO_PUBLICATION'
VERIFIED_STATE = 'PUBLISHED_VERIFIED_T1'
LEGACY_STATE = 'LEGACY_METADATA_INCOMPLETE'


def is_https(value):
    parsed = urlparse(str(value or ''))
    return parsed.scheme == 'https' and bool(parsed.netloc)


def verification_state(article, contract):
    automation = article.get('automation') or {}
    sources = article.get('sources') or []
    verified = (
        article.get('publication_mode') == 'AUTO_PUBLISHED'
        and automation.get('authority') == VERIFIED_AUTHORITY
        and automation.get('source_tier') == 'T1'
        and bool(sources)
        and all(source.get('name') and is_https(source.get('url')) for source in sources)
    )
    code = VERIFIED_STATE if verified else LEGACY_STATE
    definition = contract['verification_states'][code]
    return {
        'schema_version': contract['schema_version'],
        'article_id': article['id'],
        'state': code,
        'label': definition['public_label'],
        'distribution_eligible_as_verified': definition['distribution_eligible_as_verified'],
        'source_tier': 'T1' if verified else None,
        'derived': True,
        'contract_effective_local': contract['effective_local'],
    }


def corrections_for(article_id, registry):
    return [entry for entry in registry.get('entries', []) if entry.get('article_id') == article_id]


def validate_contract(contract, registry, article_ids):
    errors = []
    states = contract.get('verification_states') or {}
    for code in (VERIFIED_STATE, LEGACY_STATE):
        if code not in states:
            errors.append(f'missing_state:{code}')
    ownership = contract.get('ownership_disclosure') or {}
    if ownership.get('status') == 'NOT_DECLARED_CANONICALLY' and ownership.get('legal_publisher') is not None:
        errors.append('unsupported_legal_publisher')
    if not registry.get('registry_started_local'):
        errors.append('missing_registry_start')
    seen = set()
    for entry in registry.get('entries', []):
        entry_id = entry.get('id')
        if not entry_id or entry_id in seen:
            errors.append('invalid_or_duplicate_correction_id')
        seen.add(entry_id)
        if entry.get('article_id') not in article_ids:
            errors.append(f'unknown_correction_article:{entry.get("article_id")}')
        if not entry.get('published_local') or not entry.get('summary') or not entry.get('kind'):
            errors.append(f'incomplete_correction:{entry_id}')
    return errors
