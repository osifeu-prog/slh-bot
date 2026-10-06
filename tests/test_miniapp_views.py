import unittest
from pathlib import Path

class MiniAppViewsTest(unittest.TestCase):
    def setUp(self):
        self.src=Path("mini_app.html").read_text(encoding="utf-8")
    def test_view_choices_exist(self):
        for value in ("night","paper","tg","compact","normal","roomy","m","l","xl","on","off"):
            self.assertIn('data-val="'+value+'"',self.src)
        self.assertIn('id="vSheet"',self.src)
        self.assertIn('id="vClose"',self.src)
    def test_preferences_use_cloud_storage(self):
        self.assertIn("CloudStorage",self.src)
        self.assertIn("slh_view_v1",self.src)
    def test_native_controls_are_version_guarded(self):
        for token in ("isVersionAtLeast","SettingsButton","BackButton","addToHomeScreen","requestFullscreen"):
            self.assertIn(token,self.src)
    def test_transcription_errors_are_absent(self):
        for bad in ("themeParams){}","haptics!=='on'!W","map[id][]"):
            self.assertNotIn(bad,self.src)

    def test_home_shows_separate_live_bsc_slh_balance(self):
        self.assertIn('id="tokenOnchain"', self.src)
        self.assertIn("SLH · פנימי", self.src)
        self.assertIn("SLH · on-chain", self.src)
        self.assertIn("setText('tokenOnchain',liveSlh);", self.src)

if __name__=="__main__":
    unittest.main()
