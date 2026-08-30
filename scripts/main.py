import logging
from scripts.gowa_api_wrapper import GowaAPIWrapper
import config
from scripts.processor import run_processor


def main():
    # Configure logging to console with IST timestamps
    class ISTFormatter(logging.Formatter):
        def __init__(self, fmt=None, datefmt=None):
            super().__init__(fmt=fmt, datefmt=datefmt)
            from datetime import timezone, timedelta
            self.tz = timezone(timedelta(hours=5, minutes=30))

        def formatTime(self, record, datefmt=None):
            from datetime import datetime
            dt = datetime.fromtimestamp(record.created, tz=self.tz)
            return dt.isoformat()

    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)
    sh.setFormatter(ISTFormatter("%(asctime)s %(levelname)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[sh])

    logging.info('Starting Gowa checker')

    # Initialize API wrapper
    gowa_api = GowaAPIWrapper(config.BASE_URL, config.API_KEY, device_id=config.DEVICE_ID)

    # Run processor (this is blocking until processing completes)
    try:
        run_processor(gowa_api, config)
    except Exception as e:
        logging.exception(f'Processor terminated with exception: {e}')


if __name__ == '__main__':
    main()
