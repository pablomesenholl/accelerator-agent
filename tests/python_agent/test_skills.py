"""Offline tests for generic skill discovery, retrieval, and access boundaries."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'python-agent'))
from tools.file_tools import WorkspaceFiles
from tools.skill_tools import SkillLibrary, MAX_DOCUMENT_CHARS, MAX_INSTRUCTION_CHARS


class SkillLibraryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'skills'
        self.skill = self.root / 'example'
        (self.skill / 'references').mkdir(parents=True)
        (self.skill / 'SKILL.md').write_text(
            '---\nname: Example\ndescription: >-\n  A folded\n  description.\n---\n# Instructions\nSECRET_WORKFLOW\n')
        (self.skill / 'references' / 'guide.md').write_text(
            '# Guide\n## Topic\n' + '\n'.join(f'line {i} ' + 'x' * 90 for i in range(250)))
        self.library = SkillLibrary(self.root)

    def test_discovery_exposes_only_metadata(self):
        result = self.library.list_skills()
        self.assertEqual(result['skills'], [{
            'name': 'example', 'title': 'Example', 'description': 'A folded description.'}])
        self.assertNotIn('SECRET_WORKFLOW', str(result))

    def test_bad_skill_does_not_hide_good_skills(self):
        bad = self.root / 'broken'
        bad.mkdir()
        (bad / 'SKILL.md').write_text('no metadata')
        result = self.library.list_skills()
        self.assertEqual(len(result['skills']), 1)
        self.assertEqual(result['errors'][0]['name'], 'broken')
        self.assertIn('error', self.library.load_skill('broken'))
        self.assertIn('error', self.library.read_skill_document('broken'))

    def test_load_instructions_and_document_manifest(self):
        result = self.library.load_skill('example')
        self.assertIn('SECRET_WORKFLOW', result['content'])
        self.assertEqual(result['documents'], ['SKILL.md', 'references/guide.md'])
        self.assertIsNone(result['next_line'])

    def test_repeat_load_omits_content_and_a_new_library_starts_fresh(self):
        first = self.library.load_skill('example')
        repeat = self.library.load_skill('example')
        self.assertTrue(repeat['already_loaded'])
        self.assertNotIn('content', repeat)
        self.assertEqual(first['documents'], repeat['documents'])
        self.assertIn('read_skill_document', repeat['message'])
        self.assertIn('content', SkillLibrary(self.root).load_skill('example'))
        # Explicit bounded retrieval remains available for instructions and references.
        self.assertIn('content', self.library.read_skill_document('example', line_count=10))

    def test_failed_load_is_not_remembered(self):
        target = self.skill / 'SKILL.md'
        valid = target.read_text()
        target.write_text('invalid')
        self.assertIn('error', self.library.load_skill('example'))
        target.write_text(valid)
        self.assertIn('content', self.library.load_skill('example'))

    def test_bounded_paging_and_search(self):
        result = self.library.read_skill_document('example', 'references/guide.md', line_count=99999)
        self.assertLessEqual(len(result['content']), MAX_DOCUMENT_CHARS)
        self.assertLessEqual(len(result['content'].splitlines()), 120)
        page = self.library.read_skill_document(
            'example', 'references/guide.md', start_line=result['next_line'], line_count=1)
        expected = (self.skill / 'references/guide.md').read_text().splitlines()[result['next_line'] - 1]
        self.assertEqual(page['content'], expected)
        search = self.library.read_skill_document('example', 'references/guide.md', query='TOPIC')
        self.assertEqual(search['matches'], [{'line': 2, 'text': '## Topic'}])
        self.assertNotIn('content', search)
        matches = self.library.read_skill_document('example', 'references/guide.md', query='line')
        self.assertEqual(len(matches['matches']), 20)
        self.assertTrue(matches['more_matches'])

    def test_limits_are_explicit_and_recoverable(self):
        for args in [{'start_line': 0}, {'line_count': 0}, {'start_line': 10000}]:
            self.assertIn('error', self.library.read_skill_document('example', **args))
        large = self.skill / 'references/large.md'
        large.write_text('x' * (MAX_DOCUMENT_CHARS + 1))
        self.assertIn('error', self.library.read_skill_document('example', 'references/large.md'))
        instructions = self.skill / 'SKILL.md'
        instructions.write_text(instructions.read_text() + '\nshort line' * 5000)
        loaded = self.library.load_skill('example')
        self.assertLessEqual(len(loaded['content']), MAX_INSTRUCTION_CHARS)
        self.assertIsNotNone(loaded['next_line'])
        self.assertIn('content', self.library.read_skill_document('example', start_line=loaded['next_line']))

    def test_absolute_traversal_cross_skill_and_link_paths_rejected(self):
        outside = self.base / 'outside.md'
        outside.write_text('private')
        (self.skill / 'linked.md').symlink_to(outside)
        (self.skill / 'refs-link').symlink_to(self.skill / 'references', target_is_directory=True)
        (self.root / 'alias').symlink_to(self.skill, target_is_directory=True)
        (self.skill / 'hard.md').hardlink_to(outside)
        for skill, document in [
            ('../example', 'SKILL.md'), (str(self.skill), 'SKILL.md'),
            ('example', '../example/SKILL.md'), ('example', str(outside)),
            ('example', 'linked.md'), ('example', 'refs-link/guide.md'),
            ('alias', 'SKILL.md'), ('example', 'hard.md'), ('example', 'missing.md'),
        ]:
            with self.subTest(skill=skill, document=document):
                self.assertIn('error', self.library.read_skill_document(skill, document))
        self.assertNotIn('linked.md', self.library.load_skill('example')['documents'])
        self.assertTrue(any(e['name'] == 'alias' for e in self.library.list_skills()['errors']))

    def test_workspace_tools_cannot_modify_skill_files_even_with_broad_workspace(self):
        tools = WorkspaceFiles(self.base, read_only_roots=(self.root,))
        before = (self.skill / 'SKILL.md').read_text()
        self.assertIn('error', tools.write_file('skills/example/SKILL.md', 'changed'))
        self.assertIn('error', tools.edit_file('skills/example/SKILL.md', 'SECRET_WORKFLOW', 'changed'))
        self.assertNotIn('error', tools.write_file('output/test.in', 'example'))
        self.assertEqual((self.skill / 'SKILL.md').read_text(), before)
        with self.assertRaises(ValueError):
            WorkspaceFiles(self.skill / 'new-workspace', read_only_roots=(self.root,))
        self.assertFalse((self.skill / 'new-workspace').exists())

    def test_real_repository_catalog(self):
        library = SkillLibrary()
        self.assertTrue({'lattice-generator', 'lattice-validator', 'opalx-simulator', 'magnus'}
                        .issubset({s['name'] for s in library.list_skills()['skills']}))
        self.assertIn('references/opalx-input-reference.md', library.load_skill('lattice-generator')['documents'])


if __name__ == '__main__':
    unittest.main()
