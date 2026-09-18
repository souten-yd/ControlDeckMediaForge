from pathlib import Path
import importlib.util
import pytest

spec=importlib.util.spec_from_file_location('custom_runner',Path(__file__).parents[1]/'scripts/3ds_opencode_flow_e2e.py')
assert spec and spec.loader
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)


def test_custom_prompt_retains_exact_text_and_names(tmp_path: Path) -> None:
    path=tmp_path/'prompt.txt';path.write_text('実画像を評価する。\n')
    prompt,names=runner.custom_acceptance_task(path,['review.zip','trex.glb'])
    assert prompt=='実画像を評価する。\n' and names=={'review.zip','trex.glb'}


@pytest.mark.parametrize('names',[[],['../output.glb'],['a/b.glb'],['same','same'],['x']*33,['bad\nname']])
def test_custom_outputs_cannot_escape_the_delivery_directory(tmp_path: Path,names: list[str]) -> None:
    path=tmp_path/'prompt.txt';path.write_text('Prompt')
    with pytest.raises(ValueError):runner.custom_acceptance_task(path,names)


def test_custom_prompt_rejects_links_empty_and_oversized(tmp_path: Path) -> None:
    path=tmp_path/'prompt.txt';path.write_text('Prompt');link=tmp_path/'link';link.symlink_to(path)
    with pytest.raises(ValueError):runner.custom_acceptance_task(link,['result.zip'])
    for text in ('',' '*10,'x'*65537):
        path.write_text(text)
        with pytest.raises(ValueError):runner.custom_acceptance_task(path,['result.zip'])


def test_exact_mcp_scope_retains_builtin_denials_and_removes_broad_allow() -> None:
    payload = {}
    runner.restrict_tools(payload, director_static=False)
    runner.restrict_custom_mcp_scope(payload, ['media.scene.create', 'media.scene.review'])
    assert all(payload['tools'][name] is False for name in ('bash', 'read', 'edit', 'write', 'task'))
    assert payload['permission'] == {'*': 'deny', 'controldeck_addons_media_scene_create': 'allow',
                                     'controldeck_addons_media_scene_review': 'allow'}
    assert payload['agent']['build']['tools'] == {'controldeck_addons_*': False,
        'controldeck_addons_media_scene_create': True, 'controldeck_addons_media_scene_review': True}


@pytest.mark.parametrize('names', [[], ['media.*'], ['bash'], ['media.scene.create'] * 2])
def test_exact_mcp_scope_rejects_wildcards_builtins_and_duplicates(names: list[str]) -> None:
    with pytest.raises(ValueError):
        runner.restrict_custom_mcp_scope({}, names)
