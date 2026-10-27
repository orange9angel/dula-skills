"""Optional Windows current-user DPAPI vault. No plaintext credentials on disk.

Run --store interactively once (only with explicit user authorization).
The encrypted blob belongs in the ignored .suno_profile, never in Git.
"""
import ctypes
from ctypes import wintypes
import getpass,json,os,sys
from pathlib import Path
PROFILE=Path(__file__).resolve().parents[3]/'dula-story/.suno_profile'
VAULT=PROFILE/'credentials.dpapi'
class BLOB(ctypes.Structure):
    _fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_ubyte))]
def transform(payload,protect):
    if os.name!='nt':raise RuntimeError('DPAPI requires Windows')
    buf=ctypes.create_string_buffer(payload)
    source=BLOB(len(payload),ctypes.cast(buf,ctypes.POINTER(ctypes.c_ubyte)))
    target=BLOB()
    dll=ctypes.WinDLL('crypt32',use_last_error=True)
    fn=dll.CryptProtectData if protect else dll.CryptUnprotectData
    fn.restype=wintypes.BOOL
    if not fn(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:return ctypes.string_at(target.pbData,target.cbData)
    finally:
        free=ctypes.WinDLL('kernel32').LocalFree
        free.argtypes=[ctypes.c_void_p];free.restype=ctypes.c_void_p
        free(target.pbData)
def load():
    if not VAULT.exists():return {}
    return json.loads(transform(VAULT.read_bytes(),False).decode('utf-8'))
def store():
    email=getpass.getpass('Suno account (hidden): ')
    password=getpass.getpass('Suno password (hidden): ')
    if not email or not password:raise ValueError('Both fields are required')
    PROFILE.mkdir(exist_ok=True)
    payload=json.dumps({'email':email,'password':password}).encode('utf-8')
    encrypted=transform(payload,True)
    if transform(encrypted,False)!=payload:raise RuntimeError('DPAPI round-trip failed')
    VAULT.write_bytes(encrypted)
    print('Stored Windows current-user encrypted credentials; plaintext was not written.')
if __name__=='__main__':
    if sys.argv[1:]==['--store']:store()
    elif sys.argv[1:]==['--check']:
        saved=load()
        print('Local encrypted credentials available' if saved.get('password') else 'No saved credentials')
    else:raise SystemExit('Use --store or --check')
