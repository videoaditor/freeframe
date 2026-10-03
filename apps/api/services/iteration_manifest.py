"""Validated text plans and version-bound keys. No model calls or storage here."""
import hashlib
import json
import time
from typing import Literal

from jose import JWTError, jwt
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..config import settings


class Slot(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,80}$')
    label: str = Field(min_length=1, max_length=200)
    role: Literal['hook', 'opening', 'lead', 'body', 'cta']
    group: str = Field(min_length=1, max_length=200)
    script: str = Field(min_length=1, max_length=20000)


class Recipe(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,80}$')
    label: str = Field(min_length=1, max_length=200)
    slots: list[str] = Field(min_length=2, max_length=4)


class Manifest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal[1]
    summary: str = Field(min_length=1, max_length=2000)
    slots: list[Slot] = Field(min_length=2, max_length=40)
    recipes: list[Recipe] = Field(min_length=1, max_length=100)
    clarification: str | None = None


def validate_manifest(value: dict) -> dict:
    try:
        plan = Manifest.model_validate(value)
    except ValidationError as e:
        raise ValueError('The briefing structure could not be read. Clarify the sections and try again.') from e
    if plan.clarification:
        raise ValueError(plan.clarification)
    ids = {s.id: s for s in plan.slots}
    if len(ids) != len(plan.slots) or len({r.id for r in plan.recipes}) != len(plan.recipes):
        raise ValueError('The briefing contains duplicate part identifiers.')
    used, recipes = set(), set()
    for r in plan.recipes:
        if len(set(r.slots)) != len(r.slots) or any(s not in ids for s in r.slots):
            raise ValueError('A combination references a missing or repeated part.')
        if len('\n\n'.join(ids[s].script for s in r.slots))>40000:
            raise ValueError('A finished ad exceeds the 40,000-character review limit. Shorten its script.')
        roles = [ids[s].role for s in r.slots]
        legal = roles[0] in ('hook', 'opening') and roles.count('body') == 1
        rest = roles[1:]
        if rest and rest[0] == 'lead':
            legal = legal and roles[0] == 'hook'
            rest = rest[1:]
        legal = legal and rest in (['body'], ['body', 'cta'])
        if not legal or tuple(r.slots) in recipes:
            raise ValueError('A combination has repeated parts or an invalid sequence.')
        used.update(r.slots); recipes.add(tuple(r.slots))
    if used != set(ids) or any(not s.script.strip() for s in plan.slots):
        raise ValueError('Every requested part needs script text and at least one combination.')
    return plan.model_dump(exclude_none=True)


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def sign_plan(manifest, owner, project, brief, now=None):
    now = int(time.time() if now is None else now)
    return jwt.encode({'purpose': 'iteration-plan-v1', 'owner': owner, 'project': project,
                       'brief': digest(brief), 'manifest': validate_manifest(manifest), 'expires': now + 3600},
                      settings.jwt_secret, algorithm='HS256')


def read_plan(token, owner, project, brief, now=None):
    try:
        p = jwt.decode(token, settings.jwt_secret, algorithms=['HS256'])
        if (p.get('purpose') != 'iteration-plan-v1' or p.get('owner') != owner or p.get('project') != project
                or p.get('brief') != digest(brief) or p.get('expires', 0) <= (time.time() if now is None else now)):
            raise ValueError()
        return validate_manifest(p['manifest'])
    except (JWTError, KeyError, TypeError, ValueError) as e:
        raise ValueError('The briefing changed or its preview expired. Read the briefing again.') from e


def recipe_key(request_id, manifest, recipe, versions, aspect_ratio):
    slots = {s['id']: s for s in manifest['slots']}
    return digest({'request': request_id, 'recipe': recipe,
                   'parts': [{**slots[s], 'version_id': versions[s]} for s in recipe['slots']],
                   'aspect_ratio': aspect_ratio, 'contract': 1})


def review_result(value, version_id, review_key):
    if (not isinstance(value, dict) or value.get('version_id') != str(version_id)
            or value.get('review_key') != review_key or value.get('status') not in ('clear', 'held')
            or not isinstance(value.get('findings'), list)):
        return {'status': 'error', 'findings': [], 'error': 'Review unavailable. We will retry; this version is not approved.'}
    findings = value['findings']
    if any(not isinstance(f, dict) or not isinstance(f.get('body'), str) or not isinstance(f.get('must_fix'), bool) for f in findings):
        return {'status': 'error', 'findings': [], 'error': 'The review response was incomplete.'}
    return {'status': 'held' if value['status'] == 'held' or any(f['must_fix'] for f in findings) else 'clear',
            'findings': findings}
