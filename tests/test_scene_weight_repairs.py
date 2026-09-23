from __future__ import annotations
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from mediaforge.scene_recipes import SceneRecipe
from mediaforge.scene_workspace import SceneWorkspace
from mediaforge.scenes import SceneError


def run_worker(tmp_path: Path, extra: dict) -> dict:
    """A real child process drives the core result boundary, not a mocked method."""
    recipe = SceneRecipe.model_validate({'schema_version':'media-forge.scene-recipe@1','operations':[
        {'type':'rig.auto','object_id':'body','rig_object_id':'rig','name':'Person'}]})
    result = {'schema_version':'media-forge.scene-recipe-result@1','blender_version':'4.5.13',
              'autoexec_disabled':True,'operation_count':1,'stable_object_ids':['body','rig'],**extra}
    executable = tmp_path/'worker'
    executable.write_text('#!/usr/bin/python3\nfrom pathlib import Path\n'
                          "Path('scene.blend').write_bytes(b'fixture')\n"
                          f"Path('result.json').write_text({json.dumps(result)!r})\n")
    executable.chmod(0o700)
    workspace = SceneWorkspace.__new__(SceneWorkspace)
    workspace.recipe_root = tmp_path/'recipes';workspace.recipe_root.mkdir()
    workspace.recipe_worker = executable;workspace.process_timeout_sec=10
    _, facts = asyncio.run(workspace._apply_recipe_worker(recipe,SimpleNamespace(executable=executable,version='4.5.13'),source=None))
    return facts


FACT = {'object_id':'body','repaired_vertices':14,'components':1,'max_donor_distance_m':.004,
        'distance_limit_m':.005,'body_height_m':1.}


@pytest.mark.parametrize('extra',[{}, {'automatic_weight_repairs':[]}, {'automatic_weight_repairs':[FACT]}])
def test_old_empty_and_repaired_results_cross_real_core_boundary(tmp_path: Path, extra: dict) -> None:
    result=run_worker(tmp_path,extra)
    assert all(result[k]==v for k,v in extra.items())


@pytest.mark.parametrize('extra',[
    {'unknown_report':[]}, {'automatic_weight_repairs':None},
    {'automatic_weight_repairs':[FACT,FACT]},
    *[{'automatic_weight_repairs':[{**FACT,key:value}]} for key,value in [
        ('object_id','rig'),('repaired_vertices',129),('repaired_vertices',True),
        ('components',15),('body_height_m',float('nan')),('max_donor_distance_m',.02),
        ('distance_limit_m',.1),('unexpected',1)]],
])
def test_invalid_reports_still_fail_closed(tmp_path: Path, extra: dict) -> None:
    with pytest.raises(SceneError,match='scene (recipe result|mesh facts) differ'):
        run_worker(tmp_path,extra)
