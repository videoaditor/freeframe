"""Preview route contracts: a card must lead to the matching folder and usable files."""
import importlib.util
from pathlib import Path
import unittest
import json
import threading
from urllib.request import urlopen

spec = importlib.util.spec_from_file_location('preview', Path(__file__).with_name('preview-api.py'))
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


class PreviewContracts(unittest.TestCase):
    def test_http_routes_deliver_collections_and_media(self):
        server = preview.ThreadingHTTPServer(('127.0.0.1', 0), preview.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            for path in ('/requests', '/projects/p2/assets?folder_id=f3', '/projects/p1/folder-tree'):
                with urlopen(base + path) as response:
                    self.assertIsInstance(json.load(response), list)
            with urlopen(base + '/demo-media/preview.mp4') as response:
                self.assertEqual(response.headers['Content-Type'], 'video/mp4')
                self.assertGreater(len(response.read()), 100)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_every_request_has_its_own_matching_folder_and_files(self):
        for request in preview.REQUESTS:
            project = request['project_id']
            folders = preview.project_preview_response(f'/projects/{project}/folder-tree', {})
            self.assertIn(request['folder_id'], [f['id'] for f in folders])
            assets = preview.project_preview_response(f'/projects/{project}/assets', {'folder_id': [request['folder_id']]})
            self.assertIsInstance(assets, list)
            self.assertEqual(len(assets), request['assets'])
            self.assertTrue(all(a['folder_id']==request['folder_id'] for a in assets))
            for asset in assets:
                self.assertEqual(preview.project_preview_response(f"/assets/{asset['id']}", {})['id'], asset['id'])
                self.assertIsInstance(preview.project_preview_response(f"/assets/{asset['id']}/versions", {}), list)
                self.assertTrue(preview.project_preview_response(f"/assets/{asset['id']}/stream", {})['url'].endswith('.mp4'))

    def test_project_root_is_an_empty_asset_list_not_an_object(self):
        self.assertEqual(preview.project_preview_response('/projects/p1/assets', {'folder_id': ['root']}), [])
        self.assertEqual(preview.project_preview_response('/projects/p1/assets', {'folder_id': ['f3']}), [])

    def test_unknown_project_is_not_an_empty_success(self):
        self.assertIsNone(preview.project_preview_response('/projects/unknown', {}))


if __name__ == '__main__':
    unittest.main()
