"""An open object accepting a payload is not proof an LLM can discover it."""
from pathlib import Path
import json

import jsonschema
import pytest

from mediaforge.blender_compile import CompileOptions


def test_compiler_options_are_explicit_and_match_runtime() -> None:
    schema = json.loads(Path('schemas/job-request.json').read_text())
    options = schema['properties']['constraints']['properties']['compile_options']
    assert options['$ref'] == '#/$defs/CompileOptions'
    assert schema['$defs']['CompileOptions'] == CompileOptions.model_json_schema()
    request = {'operation': 'asset.pack', 'intent': 'Preserve textured shop at 30000 triangles',
               'inputs': [{'asset_id': 'asset_' + 'a' * 32}], 'profile': '3d.project.glb',
               'constraints': {'compile_options': {'schema_version': '3d.compile-options@1',
                                                   'triangle_budget': 30000}},
               'output': {'format': 'zip', 'count': 1}, 'local_only': True}
    jsonschema.validate(request, schema)
    request['constraints']['compile_options']['triangle_budget'] = 11
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(request, schema)


def test_served_agent_schema_keeps_discovery_under_host_limit(client) -> None:
    response = client.get('/schemas/job-request.json')
    assert response.status_code == 200
    assert len(response.content) < 64 * 1024
    schema = response.json()
    assert 'compile_options' in schema['properties']['constraints']['properties']
    assert schema['$defs']['CompileOptions']['additionalProperties'] is False
