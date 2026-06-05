"""Dry-run test for Ownership Registry.

Verifies all functionality actually works (not mocks/stubs).

WHO: ownership-registry:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: testing (GRAPH-002)
"""

import sys
import os
import tempfile
import shutil
sys.path.insert(0, '.')

from src.services.ownership_registry import OwnershipRegistry
from src.integrations.ontology_schema import (
    ComponentType,
    OwnershipViolationType,
)


def dry_run():
    print('=== OWNERSHIP REGISTRY DRY RUN ===\n')

    # Create temp directory
    temp_dir = tempfile.mkdtemp()
    print(f'Temp dir: {temp_dir}')

    try:
        # Initialize registry
        print('\n1. Initializing OwnershipRegistry...')
        registry = OwnershipRegistry(data_dir=temp_dir)
        registry.initialize()
        print('[OK] Registry initialized')

        # Create test file
        print('\n2. Creating test component file...')
        test_file = os.path.join(temp_dir, 'test_skill.md')
        with open(test_file, 'w') as f:
            f.write('# Test Skill\n\nThis is a test skill for GRAPH-002.')
        print(f'[OK] Test file created: {test_file}')

        # Register component
        print('\n3. Registering component...')
        success = registry.register_component(
            component_id='skill:test',
            component_type=ComponentType.SKILL,
            canonical_path=test_file,
            owner_project='memory-mcp-triple-system',
            version='1.0.0',
        )
        assert success, "Failed to register component"
        print('[OK] Component registered')

        # Retrieve component
        print('\n4. Retrieving component...')
        component = registry.get_component('skill:test')
        assert component is not None, "Failed to retrieve component"
        assert component.canonical_path == test_file, "Path mismatch"
        assert component.content_hash, "Hash not computed"
        print(f'[OK] Component retrieved: {component.id}')
        print(f'     Hash: {component.content_hash[:16]}...')

        # Verify component (should be valid)
        print('\n5. Verifying component integrity...')
        violation = registry.verify_component('skill:test')
        assert violation is None, f"Unexpected violation: {violation}"
        print('[OK] Component verified (no violations)')

        # Detect drift (should be clean)
        print('\n6. Detecting drift (no duplicates)...')
        violations = registry.detect_drift()
        assert len(violations) == 0, f"Unexpected violations: {violations}"
        print('[OK] No drift violations')

        # Create duplicate to test detection
        print('\n7. Creating duplicate file...')
        scan_dir = os.path.join(temp_dir, 'scan')
        os.makedirs(scan_dir)
        duplicate_file = os.path.join(scan_dir, 'test_skill.md')
        shutil.copy(test_file, duplicate_file)
        print(f'[OK] Duplicate created: {duplicate_file}')

        # Detect drift (should find duplicate)
        print('\n8. Detecting drift with duplicate...')
        violations = registry.detect_drift(scan_paths=[scan_dir])
        assert len(violations) > 0, "Should detect duplicate"
        assert violations[0].violation_type == OwnershipViolationType.DUPLICATE_LOCATION
        print(f'[OK] Detected {len(violations)} violation(s)')
        print(f'     Type: {violations[0].violation_type.value}')
        print(f'     Severity: {violations[0].severity}')

        # Fix violations
        print('\n9. Fixing violations...')
        results = registry.fix_violations(violations, auto_fix=True)
        assert len(results['fixed']) > 0, "Should fix violations"
        assert not os.path.exists(duplicate_file), "Duplicate should be deleted"
        print(f'[OK] Fixed {len(results["fixed"])} violation(s)')

        # Test hash mismatch detection
        print('\n10. Testing hash mismatch detection...')
        with open(test_file, 'w') as f:
            f.write('# Modified content')
        violation = registry.verify_component('skill:test')
        assert violation is not None, "Should detect hash mismatch"
        assert violation.violation_type == OwnershipViolationType.HASH_MISMATCH
        print('[OK] Hash mismatch detected')

        # Update hash
        print('\n11. Updating hash (auto-accept change)...')
        results = registry.fix_violations([violation], auto_fix=True)
        assert len(results['fixed']) > 0, "Should update hash"
        violation = registry.verify_component('skill:test')
        assert violation is None, "Should be valid after hash update"
        print('[OK] Hash updated')

        # Test persistence
        print('\n12. Testing save/load...')
        assert registry.save(), "Failed to save"
        print('[OK] Registry saved')

        registry2 = OwnershipRegistry(data_dir=temp_dir)
        assert registry2.load(), "Failed to load"
        component2 = registry2.get_component('skill:test')
        assert component2 is not None, "Failed to load component"
        print(f'[OK] Registry loaded, component retrieved: {component2.id}')

        # Test manifest export/import
        print('\n13. Testing manifest export/import...')
        manifest_path = os.path.join(temp_dir, 'manifest.json')
        assert registry.export_manifest(manifest_path), "Failed to export"
        print(f'[OK] Manifest exported: {manifest_path}')

        registry3 = OwnershipRegistry(data_dir=temp_dir + '_import')
        os.makedirs(temp_dir + '_import', exist_ok=True)
        imported = registry3.import_manifest(manifest_path)
        assert imported > 0, "Failed to import"
        print(f'[OK] Imported {imported} component(s)')

        print('\n=== ALL TESTS PASSED ===')
        print('All functionality verified as real and working!')
        return True

    except AssertionError as e:
        print(f'\n[FAIL] Assertion failed: {e}')
        return False
    except Exception as e:
        print(f'\n[FAIL] Unexpected error: {e}')
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
        if os.path.exists(temp_dir + '_import'):
            shutil.rmtree(temp_dir + '_import', ignore_errors=True)


if __name__ == '__main__':
    success = dry_run()
    sys.exit(0 if success else 1)
