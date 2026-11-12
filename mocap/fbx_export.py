"""Cancellable, transactional FBX export of the selected committed generation."""
import json
import os
from pathlib import Path
import numpy as np
from .motion_tools import selected_export
from .result_artifacts import file_stat


def _reencode(temporary, message):
    """Re-export a written skeleton FBX through the bundled Blender runtime.

    The direct writer's compact header/Definitions layout imports in Blender but
    can be rejected by strict Autodesk FBX SDK consumers such as Cascadeur;
    Blender writes the conventional full layout without changing the take.
    """
    import subprocess
    from .retarget.runtime import blender
    converted = temporary.with_name(temporary.name + '.blender.fbx')
    converted.unlink(missing_ok=True)
    message('Re-encoding through Blender (strict FBX importers)')
    command = [str(blender()), '-b', '--factory-startup', '--disable-autoexec', '--threads', '3', '--python-exit-code', '1',
               '--python', str(Path(__file__).with_name('fbx_blender_pass.py')), '--', str(temporary), str(converted)]
    env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8',
               OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    try:
        try:
            done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  encoding='utf-8', errors='replace', env=env,
                                  creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), timeout=1800)
        except subprocess.TimeoutExpired:
            raise ValueError('Blender FBX re-encode timed out')
        tail = ' | '.join(line.strip() for line in (done.stdout or '').splitlines() if line.strip())
        if done.returncode != 0 or not converted.is_file() or converted.stat().st_size == 0:
            raise ValueError('Blender FBX re-encode failed: ' + tail[-500:])
        os.replace(converted, temporary)
    finally:
        converted.unlink(missing_ok=True)


def run(request, emit=lambda *a, **k: None):
    from .blend_support import build, cleanup, partial
    from .fbx_writer import write
    from .gemx_result import is_project
    from .scene_export import context
    request=Path(request)
    if request.stat().st_size>4*1024**2:raise ValueError('Export request is too large')
    rows=json.loads(request.read_text(encoding='utf-8'))
    if not isinstance(rows,list) or not 1<=len(rows)<=4096:raise ValueError('Invalid export request')
    staged=[];origins={};committed=[];native_checks=[]
    compatibility_dirs=[]
    try:
        destinations = {Path(row['target']).resolve() for row in rows}
        if len(destinations) != len(rows):raise ValueError('Duplicate export destination')
        for i,row in enumerate(rows):
            project=Path(row['project']);kind=row['kind'];target=Path(row['target'])
            source=selected_export(project,kind)
            if source is None or source.resolve()!=Path(row['source']).resolve():
                raise ValueError('Selected target motion changed. Prepare Preview and export again.')
            if target.suffix.lower()!='.fbx':raise ValueError('Choose an FBX destination')
            temporary=partial(target,request)
            output=temporary
            work=None
            if row.get('fbx_compatibility',False):
                work=temporary
                work.mkdir()
                owner=work/'.rgbmocap-owner'
                try:
                    owner.write_text(request.stem,encoding='utf-8')
                except OSError:
                    owner.unlink(missing_ok=True)
                    work.rmdir()
                    raise
                compatibility_dirs.append(work)
                temporary=work/'source.fbx'
                output=work/'compatible.fbx'
            if is_project(project):
                from .gemx_skeleton_export import write as write_soma

                state = {'total': 1}

                def progress(done, total):
                    state['total'] = total
                    emit('progress', stage='save_fbx', current=i*total+done, total=len(rows)*total, message='Export SOMA FBX')

                staged.append((output, target, work))
                native_checks.append(write_soma(temporary, row, source, destinations, 'fbx', progress))
                if row.get('blender_convert', False):
                    _reencode(temporary, lambda text: emit('progress', stage='save_fbx',
                                                           current=(i+1)*state['total'], total=len(rows)*state['total'], message=text))
                continue
            meta=project/(kind+'_mixamo.json');info=json.loads(meta.read_text(encoding='utf-8'))
            paths=[meta,source]
            for key in ('asset_file','frames_file'):
                if Path(info[key]).name!=info[key]:raise ValueError('Invalid committed file path')
                paths.append(project/info[key])
            if destinations.intersection(p.resolve() for p in paths):raise ValueError('An export destination overlaps a committed source file.')
            stamps=[file_stat(p) for p in paths]
            scene=row.get('scene')
            if scene is not None and context(scene['root'],project)!=scene:raise ValueError('Scene placement changed. Export again.')
            staged.append((output,target,work))
            committed.append((project,kind,paths,stamps,scene))
            with np.load(project/info['asset_file'],allow_pickle=False) as data:
                needed=('parents','fbx_rest','fbx_rest_frames','fbx_display_frames','fbx_tip_local')
                if not all(k in data for k in needed):raise ValueError('FBX rest pose is unavailable. Use Prepare Preview first.')
                a={k:data[k] for k in needed}
                symmetric=None
                if row.get('symmetric_rest',False):
                    if not all(k in data for k in ('rest','ends')):raise ValueError('Symmetric rest data is unavailable. Use Prepare Preview first.')
                    symmetric=dict(rest=data['rest'],ends=data['ends'])
            frames=np.load(project/info['frames_file'],mmap_mode='r',allow_pickle=False)
            try:
                transform=np.eye(4) if scene is None else np.asarray(scene['transform'],float)
                if row.get('place_at_origin',False):
                    from .export_options import centered_transform
                    transform=centered_transform(transform,frames[0,0,:3,3],origins,row.get('origin_group',str(project)))
                def progress(done,total):
                    emit('progress',stage='save_fbx',current=i*52+done,total=len(rows)*52,message='Export FBX: '+kind)
                write(temporary,info['names'],a['parents'],a['fbx_rest'],a['fbx_rest_frames'],
                      a['fbx_display_frames'],a['fbx_tip_local'],frames,info['fps'],
                      transform=transform,progress=progress,
                      rig_name=row.get('rig_name','SourceAnimation'),prepend_tpose=row.get('prepend_tpose',False),symmetric_bind=symmetric)
            finally:frames._mmap.close()
            if row.get('blender_convert', False):
                _reencode(temporary, lambda text: emit('progress', stage='save_fbx',
                                                       current=(i+1)*52, total=len(rows)*52, message=text))
        for work in compatibility_dirs:
            build(work,'fbx_compatibility_scene.py',emit,'save_fbx')
            if not (work/'compatible.fbx').is_file():
                raise RuntimeError('Blender did not create the compatible FBX.')
            (work/'source.fbx').unlink()
        for verify in native_checks:verify()
        for project,kind,paths,stamps,scene in committed:
            if [file_stat(p) for p in paths]!=stamps or selected_export(project,kind)!=paths[1]:
                raise ValueError('Motion generation changed during export. Retry.')
            if scene is not None and context(scene['root'],project)!=scene:raise ValueError('Scene placement changed during export. Retry.')
        for temporary,target,*_ in staged:os.replace(temporary,target)
        return len(staged)
    finally:
        for output,_,work in staged:
            if work is None:output.unlink(missing_ok=True)
        for work in compatibility_dirs:cleanup(work,request)
        request.unlink(missing_ok=True)
