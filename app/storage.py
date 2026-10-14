import os, shutil
from pathlib import Path
from .config import RUNTIME, STORAGE_BACKEND

class ObjectStore:
    def __init__(self): self._client=None
    @property
    def client(self):
        if self._client is None:
            from minio import Minio
            prefix='S3' if STORAGE_BACKEND=='s3' else 'MINIO'
            self._client=Minio(os.environ[prefix+'_ENDPOINT'],access_key=os.environ[prefix+'_ACCESS_KEY'],
                secret_key=os.environ[prefix+'_SECRET_KEY'],secure=os.getenv(prefix+'_SECURE','true').lower()=='true',
                region=os.getenv(prefix+'_REGION') or None)
        return self._client
    @property
    def bucket(self): return os.getenv('S3_BUCKET' if STORAGE_BACKEND=='s3' else 'MINIO_BUCKET','risk-agent')
    def local(self,key):
        path=(RUNTIME/'objects'/key).resolve()
        if not path.is_relative_to((RUNTIME/'objects').resolve()): raise ValueError('非法对象路径')
        return path
    def put(self,key,path):
        if STORAGE_BACKEND in {'minio','s3'}:
            if not self.client.bucket_exists(self.bucket): self.client.make_bucket(self.bucket)
            self.client.fput_object(self.bucket,key,str(path))
        else:
            dst=self.local(key); dst.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(path,dst)
        return self.size(key)
    def size(self,key):
        return self.client.stat_object(self.bucket,key).size if STORAGE_BACKEND in {'minio','s3'} else self.local(key).stat().st_size
    def fetch(self,key,dst):
        if STORAGE_BACKEND in {'minio','s3'}: self.client.fget_object(self.bucket,key,str(dst))
        else: shutil.copyfile(self.local(key),dst)
        return dst
    def delete(self,key):
        if STORAGE_BACKEND in {'minio','s3'}: self.client.remove_object(self.bucket,key)
        else: self.local(key).unlink(missing_ok=True)
store=ObjectStore()

