"""Pure selection of one resumable step; current source versions always determine eligibility."""
from .iteration_manifest import recipe_key


def current_recipes(request_id, manifest, state, ratio):
    slots = state.get('slots', {})
    versions = {k: v['version_id'] for k, v in slots.items() if v.get('version_id')}
    for recipe in manifest['recipes']:
        if all(s in versions for s in recipe['slots']):
            yield recipe, recipe_key(request_id, manifest, recipe, versions, ratio)


def retryable(item, now):
    return item.get('attempts', 0) < 3 and item.get('next_attempt_at', 0) <= now


def next_action(request_id, manifest, state, ratio, now):
    slots = state.get('slots', {})
    outputs = state.get('outputs', {})
    for recipe, key in (current_recipes(request_id, manifest, state, ratio) if state.get('submitted') is True else []):
        if not all(slots[s].get('status') == 'clear' for s in recipe['slots']):
            continue
        output = outputs.get(key, {})
        common = {'key': key, 'recipe': recipe}
        if output.get('status') == 'delivered' or not retryable(output, now):
            continue
        if not output.get('job_id'):
            return {'kind': 'render', **common}
        if not output.get('asset_id'):
            return {'kind': 'poll_render', **common}
        if output.get('status') in ('reviewing', 'held', 'error'):
            return {'kind': 'review_output', 'review_generation':output.get('review_generation',0), **common}
    for slot in manifest['slots']:
        entry = slots.get(slot['id'], {})
        if entry.get('status') in ('ready', 'error', 'held') and retryable(entry, now):
            return {'kind': 'review_part', 'slot_id': slot['id'], 'slot': slot, 'version_id': entry['version_id'],'review_generation':entry.get('review_generation',0)}
    if batch_ready(request_id,manifest,state,ratio) and 'internal_handin' in state:
        delivery=state.get('delivery',{})
        if delivery.get('status')!='delivered' and retryable(delivery,now):
            return {'kind':'deliver_batch','keys':[key for _,key in current_recipes(request_id,manifest,state,ratio)]}
    return None


def batch_ready(request_id,manifest,state,ratio):
    current=list(current_recipes(request_id,manifest,state,ratio))
    return (state.get('submitted') is True and bool(current) and len(current)==len(manifest['recipes'])
        and all(state.get('slots',{}).get(s['id'],{}).get('status')=='clear' for s in manifest['slots'])
        and all(state.get('outputs',{}).get(key,{}).get('status')=='delivered' for _,key in current))


def progress(slots, outputs, total):
    delivered = sum(o.get('status') == 'delivered' for o in outputs)
    statuses = [s.get('status') for s in slots] + [o.get('status') for o in outputs]
    if total and delivered == total:
        state = 'delivered'
    elif 'error' in statuses:
        state = 'error'
    elif 'held' in statuses:
        state = 'held'
    elif not slots or any(s.get('status') in ('waiting', 'uploading', 'processing') for s in slots):
        state = 'waiting'
    elif any(s.get('status') in ('ready', 'reviewing') for s in slots) or 'reviewing' in [o.get('status') for o in outputs]:
        state = 'reviewing'
    else:
        state = 'rendering'
    return {'state': state, 'delivered': delivered, 'total': total}


def action_current(request_id, manifest, state, ratio, action):
    if action['kind']=='deliver_batch':
        return batch_ready(request_id,manifest,state,ratio) and action['keys']==[key for _,key in current_recipes(request_id,manifest,state,ratio)]
    if action['kind'] == 'review_part':
        source=state.get('slots',{}).get(action['slot_id'],{})
        return source.get('version_id')==action['version_id'] and source.get('review_generation',0)==action.get('review_generation',0)
    if action['kind']=='review_output' and state.get('outputs',{}).get(action['key'],{}).get('review_generation',0)!=action.get('review_generation',0):
        return False
    return any(key == action['key'] and all(state['slots'][s].get('status') == 'clear' for s in recipe['slots'])
               for recipe, key in current_recipes(request_id, manifest, state, ratio))
