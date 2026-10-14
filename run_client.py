# AkhavanLink — Created by Alireza Akhavan (علیرضا اخوان)
# Entry point used by PyInstaller (AkhavanLink.exe) and for "python run_client.py".
import sys

from akhavanlink.client.app import main

if __name__ == "__main__":
    sys.exit(main())
