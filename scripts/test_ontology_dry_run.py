"""Dry-run test for Ontology Bridge.

Verifies all functionality actually works (not mocks/stubs).
"""

import sys
import asyncio
import tempfile
import shutil
sys.path.insert(0, '.')

from src.services.ontology_bridge import OntologyBridge
from src.integrations.ontology_schema import (
    LifeEntity, LifeBucketType,
    ProjectEntity, ProjectRole,
    BeadsEntity, BeadsStatus,
    CrossLink, CrossLinkType
)


async def dry_run():
    print('=== ONTOLOGY BRIDGE DRY RUN ===\n')

    # Create temp directory
    temp_dir = tempfile.mkdtemp()
    print(f'Temp dir: {temp_dir}')

    try:
        # Initialize bridge
        print('\n1. Initializing OntologyBridge...')
        bridge = OntologyBridge(data_dir=temp_dir)
        await bridge.initialize()
        print('[OK] Bridge initialized')

        # Test Life entity
        print('\n2. Adding Life entity (Person)...')
        person = LifeEntity(
            id='person:test',
            bucket=LifeBucketType.PEOPLE,
            name='Test Person',
            description='Test description',
            tags=['test']
        )
        success = bridge.add_life_entity(person)
        assert success, "Failed to add life entity"
        print(f'[OK] Life entity added')

        # Retrieve Life entity
        retrieved = bridge.get_life_entity('person:test')
        assert retrieved is not None, "Failed to retrieve life entity"
        assert retrieved.name == 'Test Person', "Name mismatch"
        print(f'[OK] Life entity retrieved: {retrieved.name}')

        # Test Project entity
        print('\n3. Adding Project entity...')
        project = ProjectEntity(
            id='project:test',
            name='test-project',
            role=ProjectRole.TOOL,
            location='/test/path',
            status_percent=50
        )
        success = bridge.add_project_entity(project)
        assert success, "Failed to add project entity"
        print(f'[OK] Project entity added')

        retrieved_project = bridge.get_project_entity('project:test')
        assert retrieved_project is not None, "Failed to retrieve project"
        assert retrieved_project.status_percent == 50, "Status mismatch"

        # Test Beads entity
        print('\n4. Adding Beads entity (Task)...')
        task = BeadsEntity(
            id='task:test',
            title='Test task',
            status=BeadsStatus.OPEN,
            project_id='project:test',
            estimated_minutes=60
        )
        success = bridge.add_beads_entity(task)
        assert success, "Failed to add beads entity"
        print(f'[OK] Beads entity added')

        retrieved_task = bridge.get_beads_entity('task:test')
        assert retrieved_task is not None, "Failed to retrieve task"
        assert retrieved_task.title == 'Test task', "Title mismatch"

        # Test cross-link
        print('\n5. Adding cross-link (Person -> Task)...')
        link = CrossLink(
            source_id='person:test',
            source_ontology='life',
            target_id='task:test',
            target_ontology='beads',
            link_type=CrossLinkType.PERSON_OWNS_TASK,
            confidence=1.0
        )
        success = bridge.add_cross_link(link)
        assert success, "Failed to add cross-link"
        print(f'[OK] Cross-link added')

        # Verify cross-link
        links = bridge.get_cross_links('person:test')
        assert len(links) > 0, "No cross-links found"
        assert links[0].target_id == 'task:test', "Target ID mismatch"
        print(f'[OK] Cross-links retrieved: {len(links)} link(s)')

        # Test mode-aware query
        print('\n6. Testing mode-aware query (execution mode)...')
        results = await bridge.query('test', mode='execution')
        assert 'beads' in results, "Missing beads results"
        assert 'memory' in results, "Missing memory results"
        assert 'life' in results, "Missing life results"
        assert 'projects' in results, "Missing projects results"
        beads_count = len(results['beads'])
        life_count = len(results['life'])
        print(f'[OK] Query results: beads={beads_count}, life={life_count}')

        # Test save/load
        print('\n7. Testing save/load...')
        save_success = bridge.save()
        assert save_success, "Failed to save graph"
        print('[OK] Graph saved')

        bridge2 = OntologyBridge(data_dir=temp_dir)
        load_success = bridge2.load()
        assert load_success, "Failed to load graph"

        retrieved2 = bridge2.get_life_entity('person:test')
        assert retrieved2 is not None, "Failed to retrieve after load"
        assert retrieved2.name == 'Test Person', "Name mismatch after load"
        print(f'[OK] Graph loaded, entity retrieved: {retrieved2.name}')

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


if __name__ == '__main__':
    success = asyncio.run(dry_run())
    sys.exit(0 if success else 1)
