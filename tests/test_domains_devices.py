import unittest

import helpers
from watchcats.devices import detect
from watchcats.domains import DomainMap
from watchcats.presentation import display_key


class DomainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dm = DomainMap.load(str(helpers.FIX / "cache-domains"))

    def test_exact_and_wildcard(self):
        self.assertEqual(self.dm.lookup("egdownload.fastly-edge.com"), "epicgames")
        self.assertEqual(self.dm.lookup("geo.prod.do.dsp.mp.microsoft.com"), "wsus")
        self.assertEqual(self.dm.lookup("tas01.cwsapp.update.microsoft.com"), "wsus")
        self.assertEqual(self.dm.lookup("uef.np.dl.playstation.net"), "sony")
        self.assertEqual(self.dm.lookup("xvcf1.xboxlive.com"), "xboxlive")

    def test_wildcard_does_not_match_bare_domain_and_unknown(self):
        self.assertIsNone(self.dm.lookup("windowsupdate.com"))
        self.assertIsNone(self.dm.lookup("unknown.example.org"))
        self.assertIsNone(self.dm.lookup(""))


class DeviceTests(unittest.TestCase):
    def kind(self, ua):
        r = detect(ua)
        return r[0] if r else None

    def test_real_user_agents(self):
        self.assertEqual(self.kind("libhttp/14.00 (PlayStation 5)"), "ps5")
        self.assertEqual(self.kind("EpicGamesLauncher/20.3.4-58704177+++UE5+Release-Distro-5.5 (http-eventloop) Windows/10.0.26200.1.256.64bit"), "windows")
        self.assertEqual(self.kind("EpicOnlineServicesInstallHelper/5.8.0-57919941+++UE5 (http-eventloop) Windows/10.0.26200.1.256.64bit"), "windows")
        self.assertEqual(self.kind("Valve/Steam HTTP Client 1.0"), "pc")
        self.assertEqual(self.kind("curl/8.5.0"), "tool")
        self.assertIsNone(self.kind("SomethingElse/1.0"))

    def test_higher_confidence_wins(self):
        self.assertEqual(self.kind("Valve/Steam HTTP Client Windows/10.0"), "windows")

    def test_xbox_split(self):
        self.assertEqual(display_key("xboxlive", "xbox_console"), "xbox_console")
        self.assertEqual(display_key("xboxlive", "windows"), "xbox_windows")
        self.assertEqual(display_key("steam", "windows"), "steam")


if __name__ == "__main__":
    unittest.main()
