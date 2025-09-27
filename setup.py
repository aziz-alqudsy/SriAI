#!/usr/bin/env python3
"""
Setup script for SriAI - Automated setup and validation
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def check_python_version():
    """Check if Python version is 3.8+"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ is required")
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    return True

def check_ffmpeg():
    """Check if FFmpeg is installed and accessible"""
    try:
        result = subprocess.run(['ffmpeg', '-version'],
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ FFmpeg found")
            return True
    except FileNotFoundError:
        pass

    print("❌ FFmpeg not found")
    print("Please install FFmpeg:")
    print("  Windows: https://ffmpeg.org/download.html")
    print("  macOS: brew install ffmpeg")
    print("  Linux: sudo apt install ffmpeg")
    return False

def install_requirements():
    """Install Python requirements"""
    try:
        print("📦 Installing Python packages...")
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'],
                              check=True, capture_output=True, text=True)
        print("✅ Python packages installed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install packages: {e}")
        print(e.stdout)
        print(e.stderr)
        return False

def setup_env_file():
    """Create .env file from template if it doesn't exist"""
    env_path = Path('.env')
    example_path = Path('.env.example')

    if not env_path.exists():
        if example_path.exists():
            shutil.copy(example_path, env_path)
            print("✅ Created .env file from template")
            print("⚠️  Please edit .env with your API keys and tokens")
            return True
        else:
            print("❌ .env.example not found")
            return False
    else:
        print("✅ .env file already exists")
        return True

def validate_env_file():
    """Check if required environment variables are set"""
    env_path = Path('.env')
    if not env_path.exists():
        return False

    required_vars = [
        'DISCORD_TOKEN',
        'GEMINI_API_KEY',
        'YOUTUBE_STREAM_KEY'
    ]

    missing_vars = []

    with open(env_path, 'r') as f:
        content = f.read()
        for var in required_vars:
            if f"{var}=your_" in content or f"{var}=" not in content:
                missing_vars.append(var)

    if missing_vars:
        print(f"⚠️  Please set these variables in .env: {', '.join(missing_vars)}")
        return False
    else:
        print("✅ Environment variables configured")
        return True

def test_imports():
    """Test if all required modules can be imported"""
    modules = [
        'discord',
        'whisper',
        'pyttsx3',
        'google.generativeai',
        'dotenv'
    ]

    failed = []
    for module in modules:
        try:
            __import__(module)
        except ImportError:
            failed.append(module)

    if failed:
        print(f"❌ Failed to import: {', '.join(failed)}")
        return False
    else:
        print("✅ All required modules can be imported")
        return True

def main():
    print("🤖 SriAI Setup Script")
    print("=" * 40)

    all_good = True

    # Check requirements
    all_good &= check_python_version()
    all_good &= check_ffmpeg()

    # Setup
    if all_good:
        all_good &= install_requirements()

    if all_good:
        all_good &= setup_env_file()
        validate_env_file()  # Warning only

    if all_good:
        all_good &= test_imports()

    print("\n" + "=" * 40)

    if all_good:
        print("🎉 Setup completed successfully!")
        print("\nNext steps:")
        print("1. Edit .env with your API keys")
        print("2. Set up your Discord bot permissions")
        print("3. Run: python main.py")
    else:
        print("❌ Setup completed with errors")
        print("Please fix the issues above and try again")

    return 0 if all_good else 1

if __name__ == "__main__":
    sys.exit(main())