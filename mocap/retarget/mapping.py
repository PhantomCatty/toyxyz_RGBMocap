import json
from pathlib import Path

import numpy as np
A = np.array([[1.0, 0, 0], [0, 0, -1], [0, 1, 0]])
NAMES = ['Hips', 'LeftUpLeg', 'RightUpLeg', 'Spine', 'LeftLeg', 'RightLeg', 'Spine1', 'LeftFoot', 'RightFoot', 'Spine2', 'LeftToeBase', 'RightToeBase', 'Neck', 'LeftShoulder', 'RightShoulder', 'Head', 'LeftArm', 'RightArm', 'LeftForeArm', 'RightForeArm', 'LeftHand', 'RightHand']
PARENTS = np.array([-1, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9, 12, 13, 14, 16, 17, 18, 19])
VRM = ['hips', 'leftUpperLeg', 'rightUpperLeg', 'spine', 'leftLowerLeg', 'rightLowerLeg', 'chest', 'leftFoot', 'rightFoot', 'upperChest', 'leftToes', 'rightToes', 'neck', 'leftShoulder', 'rightShoulder', 'head', 'leftUpperArm', 'rightUpperArm', 'leftLowerArm', 'rightLowerArm', 'leftHand', 'rightHand']
PMX = ['下半身', '足.L', '足.R', '上半身', 'ひざ.L', 'ひざ.R', '上半身1', '足首.L', '足首.R', '上半身2', 'つま先.L', 'つま先.R', '首', '肩.L', '肩.R', '頭', '腕.L', '腕.R', 'ひじ.L', 'ひじ.R', '手首.L', '手首.R']


def load_custom_spec(path):
    """Read an explicit sidecar bone-mapping JSON; never guess bone roles.

    Returns (body, fingers, swap): body maps the 22 humanoid slots above to
    bone names in the character file; fingers is None, 'vrm_style' or an
    explicit VRM-style semantic dict; swap enables the swap_sides option
    for rigs whose .L/.R bone names are geometrically mirrored.
    """
    spec = json.loads(Path(path).read_text(encoding='utf8'))
    if not isinstance(spec, dict) or not isinstance(spec.get('body'), dict):
        raise ValueError('A custom bone-mapping JSON needs a "body" object with the 22 humanoid slots (Hips, Spine, LeftUpLeg, ...).')
    swap = spec.get('swap_sides', False)
    if not isinstance(swap, bool):
        raise ValueError('swap_sides must be true or false.')
    return spec['body'], spec.get('fingers'), swap


def swap_body_sides(body):
    ''' Exchange Left*/Right* slot bones for geometrically mirrored rigs.'''
    swapped = dict(body)
    for part in ('UpLeg', 'Leg', 'Foot', 'ToeBase', 'Shoulder', 'Arm', 'ForeArm', 'Hand'):
        left, right = 'Left' + part, 'Right' + part
        if left not in swapped or right not in swapped:
            raise ValueError('swap_sides needs both slot bones for: ' + left + ', ' + right)
        swapped[left], swapped[right] = body[right], body[left]
    return swapped


def custom_finger_semantic(fingers, bones, swap=False):
    """Optional finger table keyed with VRM semantics (leftThumbProximal...)."""
    names = set(bones)
    if fingers is None:
        return {}
    if isinstance(fingers, str):
        if fingers != 'vrm_style':
            raise ValueError('Unsupported "fingers" style: ' + fingers + ' (use "vrm_style" or an explicit mapping)')
        semantic = {}
        sides = (('left', '.R'), ('right', '.L')) if swap else (('left', '.L'), ('right', '.R'))
        for side, suffix in sides:
            for finger in ('Thumb', 'Index', 'Middle', 'Ring', 'Little'):
                for part in ('Proximal', 'Intermediate', 'Distal'):
                    bone = finger + part + suffix
                    if bone in names:
                        semantic[side + finger + part] = bone
        return semantic
    if not isinstance(fingers, dict):
        raise ValueError('The "fingers" entry must be "vrm_style", an explicit mapping object, or absent.')
    unknown = sorted({bone for bone in fingers.values() if bone not in names})
    if unknown:
        raise ValueError('The custom finger mapping names bones that do not exist: ' + ', '.join(unknown))
    return dict(fingers)

def body_trajectory_root(parents, mapped):
    """Use the body's existing root; independent control trees may coexist."""
    roots = set()
    for name in mapped:
        seen = set()
        while True:
            if name not in parents or name in seen:
                raise ValueError('Invalid humanoid bone hierarchy.')
            seen.add(name)
            parent = parents[name]
            if parent is None:
                roots.add(name)
                break
            name = parent
    if len(roots) != 1:
        raise ValueError('The mapped humanoid body must share one hierarchy root.')
    return next(iter(roots))

def body_mapping(kind,bones,semantic):
    names=set(bones)
    if kind=='custom':
        body=semantic if isinstance(semantic,dict) else {}
        mapping=[body.get(n) for n in NAMES]
        missing=[n for n,v in zip(NAMES,mapping) if not v or v not in names]
        if missing:raise ValueError('Incomplete custom bone mapping. Missing or unknown bones for: '+', '.join(missing))
        if len(set(mapping))!=22:raise ValueError('Custom humanoid bones must have distinct mappings')
        return mapping
    if kind=='mixamo':
        suffix={}
        for name in names:
            suffix.setdefault(name.split(':')[-1],[]).append(name)
        mapping=[suffix.get(n,[]) for n in NAMES]
        missing=[n for n,v in zip(NAMES,mapping) if len(v)!=1]
        if missing:raise ValueError('Expected a Mixamo humanoid rig. Missing or ambiguous bones: '+', '.join(missing)+
            '. For a custom skeleton, place an explicit bone-mapping JSON next to the FBX (named <file>.fbx.json).')
        return [v[0] for v in mapping]
    mapping=[semantic.get(n) for n in VRM] if kind=='vrm' else PMX
    missing=[NAMES[i] for i,n in enumerate(mapping) if n not in names]
    if missing:raise ValueError('Unsupported humanoid mapping (manual mapping is not available yet): '+', '.join(missing))
    if len(set(mapping))!=22:raise ValueError('Humanoid bones must have distinct mappings')
    return mapping
