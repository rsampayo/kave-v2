"""Test script for ngrok integration."""

import importlib.util
import os
import unittest


# Check if the scripts directory is properly set up as a package
def can_import_scripts() -> bool:
    """Test if the scripts package can be imported."""
    try:
        import scripts

        return bool(scripts)  # Use scripts to avoid unused import warning
    except ImportError:
        return False


class TestNgrokIntegration(unittest.TestCase):
    """Test the ngrok integration."""

    def test_scripts_package_exists(self) -> None:
        """Test that the scripts package exists and can be imported."""
        self.assertTrue(
            os.path.exists("scripts/__init__.py"), "scripts/__init__.py does not exist"
        )
        self.assertTrue(can_import_scripts(), "Failed to import scripts package")

    def test_ngrok_script_exists(self) -> None:
        """Test that the ngrok script exists."""
        self.assertTrue(
            os.path.exists("scripts/start_ngrok.py"),
            "scripts/start_ngrok.py does not exist",
        )

    def test_webhook_script_exists(self) -> None:
        """Test that the webhook script exists."""
        self.assertTrue(
            os.path.exists("scripts/start_local_with_webhook.py"),
            "scripts/start_local_with_webhook.py does not exist",
        )

    def test_ngrok_settings_class(self) -> None:
        """Test the NgrokSettings class."""
        # Use importlib to import the module without executing it
        spec = importlib.util.spec_from_file_location(
            "start_ngrok", "scripts/start_ngrok.py"
        )
        if spec is None or spec.loader is None:
            self.fail("Failed to load scripts/start_ngrok.py")
            return

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Test that the NgrokSettings class exists and has expected attributes
        self.assertTrue(
            hasattr(module, "NgrokSettings"), "NgrokSettings class not found"
        )

        settings = module.NgrokSettings()
        self.assertTrue(
            hasattr(settings, "NGROK_AUTH_TOKEN"), "NGROK_AUTH_TOKEN not found"
        )
        self.assertTrue(hasattr(settings, "NGROK_REGION"), "NGROK_REGION not found")
        self.assertTrue(
            hasattr(settings, "NGROK_LOCAL_PORT"), "NGROK_LOCAL_PORT not found"
        )
        self.assertTrue(hasattr(settings, "WEBHOOK_PATH"), "WEBHOOK_PATH not found")


if __name__ == "__main__":
    unittest.main()
