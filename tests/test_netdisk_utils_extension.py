import unittest

from src.utils.netdisk_utils import (
    FRONTEND_DISPLAY_NETDISK_OPTIONS,
    extract_canonical_resource_key,
    match_netdisk_link,
)


class NetdiskUtilsExtensionTest(unittest.TestCase):
    def test_frontend_display_options_count(self):
        # 26 种规则 + 1 种"其他" = 27 种可选项
        self.assertEqual(27, len(FRONTEND_DISPLAY_NETDISK_OPTIONS))
        self.assertIn("TeraBox", FRONTEND_DISPLAY_NETDISK_OPTIONS)
        self.assertIn("Google Drive", FRONTEND_DISPLAY_NETDISK_OPTIONS)
        self.assertIn("MEGA", FRONTEND_DISPLAY_NETDISK_OPTIONS)
        self.assertIn("GoFile", FRONTEND_DISPLAY_NETDISK_OPTIONS)
        self.assertIn("OneDrive", FRONTEND_DISPLAY_NETDISK_OPTIONS)
        self.assertIn("城通网盘", FRONTEND_DISPLAY_NETDISK_OPTIONS)
        self.assertIn("其他", FRONTEND_DISPLAY_NETDISK_OPTIONS)

    def test_match_new_netdisk_links(self):
        # TeraBox
        self.assertEqual("TeraBox", match_netdisk_link("https://terabox.com/s/1abcDEF_xyz"))
        self.assertEqual("TeraBox", match_netdisk_link("https://1024tera.com/s/1abcDEF_xyz"))

        # Google Drive
        self.assertEqual("Google Drive", match_netdisk_link("https://drive.google.com/file/d/1abcDEF_xyz/view"))
        self.assertEqual("Google Drive", match_netdisk_link("https://docs.google.com/drive/folders/1abcDEF_xyz"))

        # MEGA
        self.assertEqual("MEGA", match_netdisk_link("https://mega.nz/file/abc12345#secretkey"))
        self.assertEqual("MEGA", match_netdisk_link("https://mega.co.nz/folder/folder123#secretkey"))

        # GoFile
        self.assertEqual("GoFile", match_netdisk_link("https://gofile.io/d/abc123XYZ"))

        # OneDrive
        self.assertEqual("OneDrive", match_netdisk_link("https://1drv.ms/u/s!Abc123xyz_456"))
        self.assertEqual("OneDrive", match_netdisk_link("https://onedrive.live.com/redux/?resid=1234567890"))

        # 城通网盘
        self.assertEqual("城通网盘", match_netdisk_link("https://ctfile.com/f/123456-7890"))
        self.assertEqual("城通网盘", match_netdisk_link("https://pipipan.com/file/123456-7890"))

    def test_extract_canonical_keys_for_new_netdisks(self):
        self.assertEqual("terabox:1abcDEF_xyz", extract_canonical_resource_key("https://terabox.com/s/1abcDEF_xyz?utm=test"))
        self.assertEqual("googledrive:1abcDEF_xyz", extract_canonical_resource_key("https://drive.google.com/file/d/1abcDEF_xyz"))
        self.assertEqual("mega:abc12345", extract_canonical_resource_key("https://mega.nz/file/abc12345#secretkey"))
        self.assertEqual("gofile:abc123XYZ", extract_canonical_resource_key("https://gofile.io/d/abc123XYZ"))
        self.assertEqual("onedrive:Abc123xyz_456", extract_canonical_resource_key("https://1drv.ms/u/s!Abc123xyz_456"))
        self.assertEqual("ctfile:123456-7890", extract_canonical_resource_key("https://ctfile.com/f/123456-7890"))


if __name__ == "__main__":
    unittest.main()
