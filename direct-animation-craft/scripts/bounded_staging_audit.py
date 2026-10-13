"""Finite standing performances: fail closed on missing sampled geometry metrics.

Disjoint rendered world AABBs prove separation at a sampled pose only. An AABB
overlap is a conservative failure, not proof that triangles intersect.
"""
import math


def audit_bounded_staging(data, config):
    errors, violations, stats = [], {}, {}
    fps = data.get('fps', 0)
    finite = lambda x: type(x) in (int, float) and math.isfinite(x)
    if not finite(fps) or fps < config.get('fps_min', 30):
        return {'passed': False, 'errors': ['invalid/insufficient fps'], 'violations': [], 'stats': {}}
    actors = config.get('actors', [])
    window = config.get('window', [])
    if not actors or len(window) != 2 or not all(finite(x) for x in window) or not 0 <= window[0] < window[1]:
        return {'passed': False, 'errors': ['invalid required actors/window'], 'violations': [], 'stats': {}}
    ticks, last = {}, -math.inf
    for f in data.get('frames', []):
        t = f.get('t')
        if not finite(t) or t <= last:
            errors.append('nonfinite/nonmonotonic timestamp'); continue
        last = t; tick = round(t*fps)
        if tick in ticks or abs(t-tick/fps) > .0011:
            errors.append('duplicate/off-grid timestamp')
        ticks[tick] = f
    def problem(key, t, detail):
        row = violations.setdefault(key, {'key':key,'first_t':t,'last_t':t,'count':0,'example':detail})
        row['last_t'] = t; row['count'] += 1
    def check(key, value, low, high, t):
        if not finite(value):
            problem(key,t,'missing/nonfinite metric'); return
        stat=stats.setdefault(key,{'min':value,'max':value})
        stat['min']=min(stat['min'],value);stat['max']=max(stat['max'],value)
        if value < low-1e-8 or value > high+1e-8:
            problem(key,t,f'{value:g} outside [{low:g}, {high:g}]')
    def vector(value, n):
        return isinstance(value,list) and len(value)==n and all(finite(x) for x in value)
    previous = {}; contacts = {}; missing = 0; count = 0
    for tick in range(math.ceil(window[0]*fps-1e-7),math.ceil(window[1]*fps-1e-7)):
        f=ticks.get(tick)
        if not f:
            missing+=1;previous={};continue
        count+=1;t=f['t'];m=f.get('metrics') or {}
        check('actorGap',m.get('actorGap'),config['min_actor_gap'],math.inf,t)
        check('cameraEnvironmentGap',m.get('cameraEnvironmentGap'),config['min_camera_gap'],math.inf,t)
        for actor in actors:
            a=m.get(actor) or {}
            for field,low,high in [('vertices',1,math.inf),('boneError',0,config['max_bone_error']),
                ('minEnvironmentGap',config['min_environment_gap'],math.inf),('cameraDistance',config['min_camera_distance'],math.inf),
                ('maxArmAngle',0,config['max_arm_angle']),('headTurn',0,config['max_head_turn'])]:
                check(f'{actor}:{field}',a.get(field),low,high,t)
            sole=a.get('soleY')
            if 'min_self_gap' in config:
                for pair in config['self_pairs']:
                    check(f'{actor}:self:{pair}',(a.get('selfGaps') or {}).get(pair),config['min_self_gap'],math.inf,t)
            if not vector(sole,2):problem(actor+':soles',t,'need two finite rendered sole heights')
            else:
                supporting=0
                for side,y in zip(('left','right'),sole):
                    foot=(a.get('feet') or {}).get(side) or {}
                    if 'support' not in config:
                        check(f'{actor}:sole:{side}',y,*config['sole_y'],t);continue
                    rule=config['support'];stance=foot.get('stance');name=foot.get('contact')
                    pos,forward=foot.get('position'),foot.get('forward')
                    if type(stance) is not bool or not isinstance(name,str) or not name or not vector(pos,3) or not vector(forward,3):
                        problem(f'{actor}:foot:{side}',t,'missing stance/contact/world transform');continue
                    check(f'{actor}:sole:{side}',y,config['sole_y'][0],config['sole_y'][1] if stance else rule['max_swing_height'],t)
                    if stance:
                        supporting+=1;key=(actor,side,name)
                        if key in contacts:
                            anchor,direction=contacts[key]
                            check(f'{actor}:footSlip:{side}',math.dist(pos,anchor),0,rule['max_slip'],t)
                            check(f'{actor}:footTurn:{side}',math.dist(forward,direction),0,rule['max_turn_delta'],t)
                        else:contacts[key]=(pos,forward)
                if 'support' in config and supporting<config['support'].get('min_stance_feet',1):
                    problem(actor+':support',t,'insufficient planted feet')
            root,wrists=a.get('root'),a.get('wrists')
            valid=vector(root,3) and isinstance(wrists,list) and len(wrists)==2 and all(vector(w,3) for w in wrists)
            if not valid:problem(actor+':trajectory',t,'missing root or wrist world positions');previous.pop(actor,None)
            else:
                if actor in previous:
                    p=previous[actor]
                    check(actor+':rootStep',math.dist(root,p[0]),0,config['max_root_step'],t)
                    check(actor+':wristStep',max(math.dist(a,b) for a,b in zip(wrists,p[1])),0,config['max_wrist_step'],t)
                previous[actor]=(root,wrists)
        for shot in config.get('framing',[]):
            if f.get('entry') not in shot['entries']:continue
            key=shot['target'];focus=(m.get('focus') or {}).get(key) or {}
            p=(m.get(key) or {}).get('headProjection') if key in actors else focus.get('projection')
            if not vector(p,3):problem('framing:'+key,t,'missing projection');continue
            check(key+':screenX',abs(p[0]),0,shot.get('max_ndc',.8),t)
            check(key+':screenY',abs(p[1]),0,shot.get('max_ndc',.8),t)
            check(key+':clipZ',p[2],-1,1,t)
            if 'min_pixels' in shot:check(key+':pixels',focus.get('pixels'),shot['min_pixels'],math.inf,t)
            if shot.get('require_unblocked') and focus.get('blocked') is not False:problem(key+':occlusion',t,'focus ray blocked or absent')
    if missing:errors.append(f'{missing} missing required frame ticks')
    return {'passed':not errors and not violations,'frames':count,'errors':errors,
        'violations':list(violations.values()),'stats':stats,
        'scope':'sampled world-AABB separation, floor, limb length, bounded trajectory and declared focus projection; no artistic or continuous-collision approval'}
