from django.apps import AppConfig
import logging


class ReceiptsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "receipts"
    _moto_server = None

    def ready(self):
        import os
        import socket
        from django.conf import settings
        logger = logging.getLogger('receipts')
        logger.info(f"You Owe started - DEBUG={settings.DEBUG}")

        if not settings.DEBUG or os.environ.get('AWS_ENDPOINT_URL_S3'):
            return  # production, or dev with real Tigris — do nothing
        if ReceiptsConfig._moto_server is not None:
            return  # idempotent (ready() may be called multiple times)

        os.environ.setdefault('BUCKET_NAME', 'receipts-dev')
        os.environ.setdefault('AWS_ACCESS_KEY_ID', 'test')
        os.environ.setdefault('AWS_SECRET_ACCESS_KEY', 'test')
        os.environ.setdefault('AWS_REGION', 'us-east-1')

        # Use machine hostname so presigned URLs are reachable from browsers on other machines
        hostname = socket.gethostname()
        endpoint_url = f'http://{hostname}:5566'
        os.environ['AWS_ENDPOINT_URL_S3'] = endpoint_url

        port_in_use = False
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('0.0.0.0', 5566))
            except OSError:
                port_in_use = True

        if port_in_use:
            logger.info(f"Moto S3 port 5566 already in use, reusing existing server at {endpoint_url}")
            return

        from moto.server import ThreadedMotoServer
        server = ThreadedMotoServer(port=5566)
        server.start()
        ReceiptsConfig._moto_server = server

        import boto3
        from botocore.client import Config
        s3 = boto3.client('s3', endpoint_url=endpoint_url,
                          config=Config(s3={'addressing_style': 'path'}))
        s3.create_bucket(Bucket='receipts-dev')
        logger.info(f"Started moto S3 server at {endpoint_url}")
