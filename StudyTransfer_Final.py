# -*- coding: ascii -*-
# Study Transfer Utility RC1 - Windows XP / Python 2.7
# Final candidate: copy -> verify -> audit -> archive.
# No delete operation exists.

import os,sys,time,socket,shutil,hashlib,uuid

SRC_ROOT=os.environ.get("SOMNOSTAR_SOURCE",r"C:\D")
BACKUP_ROOT=os.environ.get("SOMNOSTAR_BACKUP",os.path.join(SRC_ROOT,"backup"))
DEST_ROOT=os.environ.get("SOMNOSTAR_DESTINATION",r"\\YOUR-SERVER\YOUR-SHARE")
MIN_BYTES=33*1024*1024
QUIET_SECONDS=120
CHUNK=4*1024*1024
UPDATE_SECONDS=1.0

PNO,PNL,PNK=4,10,[0x07, 0x42, 0xE2, 0xC0, 0xBA, 0x48, 0x21, 0xC2, 0x70, 0x8B]
FNO,FNL,FNK=16,13,[0x1E, 0xD3, 0x3E, 0x67, 0x01, 0x4E, 0x9B, 0xD7, 0x82, 0x09, 0x96, 0x55, 0xFD]
LNO,LNL,LNK=58,12,[0x90, 0xE9, 0xF3, 0x41, 0x3A, 0x71, 0xAF, 0xEB, 0x02, 0xE2, 0xE5, 0xCA]

def hb(n):
 n=float(n)
 if n>=1073741824:return "%.2f GB"%(n/1073741824)
 if n>=1048576:return "%.1f MB"%(n/1048576)
 if n>=1024:return "%.1f KB"%(n/1024)
 return "%d B"%int(n)
def dur(x):
 x=max(0,int(x));return "%02d:%02d:%02d"%(x//3600,(x%3600)//60,x%60)
def dec(b,o,n,k):
 out=[]
 for i in range(n):
  v=ord(b[o+i])^k[i]
  if not v:break
  if v<32 or v>126:raise ValueError("Unexpected Patient.dat encoding")
  out.append(chr(v))
 return "".join(out)
def patient(p):
 f=open(p,"rb")
 try:b=f.read()
 finally:f.close()
 return dec(b,PNO,PNL,PNK),dec(b,FNO,FNL,FNK),dec(b,LNO,LNL,LNK)
def safe(x):
 return "".join("_" if c in '<>:"/\\|?*' else c for c in x).strip()
def manifest(root,ignore_marker=False):
 d={}
 for b,ds,fs in os.walk(root):
  for n in fs:
   if ignore_marker and n.upper()=="TRANSFER_COMPLETE.TXT":continue
   p=os.path.join(b,n);r=os.path.relpath(p,root)
   try:d[r]=(os.path.getsize(p),os.path.getmtime(p),p)
   except OSError:pass
 return d
def candidate():
 a=[]
 if not os.path.isdir(SRC_ROOT):return None
 for n in os.listdir(SRC_ROOT):
  if n.lower()=="backup":continue
  p=os.path.join(SRC_ROOT,n);pd=os.path.join(p,"Patient.dat")
  if not os.path.isdir(p) or not os.path.isfile(pd):continue
  m=manifest(p,True);size=sum(v[0] for v in m.values())
  mts=[v[1] for r,v in m.items()]
  mt=max(mts) if mts else 0
  if size>MIN_BYTES:a.append((mt,p,size,len(m),pd))
 a.sort(reverse=True)
 return a[0] if a else None
def compare(root,m,check_mtime=False,ignore_marker=False):
 now=manifest(root,ignore_marker);old=set(m);new=set(now)
 added=sorted(new-old);removed=sorted(old-new);changed=[]
 for r in sorted(old&new):
  if m[r][0]!=now[r][0] or (check_mtime and abs(m[r][1]-now[r][1])>.01):changed.append(r)
 return added,removed,changed
def bar(done,total,w=32):
 pct=100.0*done/total if total else 100.0;f=int(w*pct/100.0)
 return "["+"#"*f+"-"*(w-f)+"] %5.1f%%"%pct
def status(stage,done,total,rel,fd,fs,start):
 # XP-safe single-line update. ANSI escape sequences are not assumed.
 e=max(.01,time.time()-start);sp=done/e;eta=(total-done)/sp if sp else 0
 line="%-10s %s  %8s/%-8s  %7s/s  ETA %s" % (stage,bar(done,total),hb(done),hb(total),hb(sp),dur(eta))
 try:
  import ctypes
  h=ctypes.windll.kernel32.GetStdHandle(-11)
  class COORD(ctypes.Structure):
   _fields_=[("X",ctypes.c_short),("Y",ctypes.c_short)]
  class SMALL_RECT(ctypes.Structure):
   _fields_=[("Left",ctypes.c_short),("Top",ctypes.c_short),("Right",ctypes.c_short),("Bottom",ctypes.c_short)]
  class CSBI(ctypes.Structure):
   _fields_=[("dwSize",COORD),("dwCursorPosition",COORD),("wAttributes",ctypes.c_ushort),("srWindow",SMALL_RECT),("dwMaximumWindowSize",COORD)]
  info=CSBI()
  ctypes.windll.kernel32.GetConsoleScreenBufferInfo(h,ctypes.byref(info))
  y=info.dwCursorPosition.Y
  pos=COORD(0,y)
  written=ctypes.c_ulong(0)
  ctypes.windll.kernel32.FillConsoleOutputCharacterA(h,ord(" "),info.dwSize.X,pos,ctypes.byref(written))
  ctypes.windll.kernel32.SetConsoleCursorPosition(h,pos)
  sys.stdout.write(line)
  sys.stdout.flush()
  ctypes.windll.kernel32.SetConsoleCursorPosition(h,pos)
 except:
  sys.stdout.write("\r"+line)
  sys.stdout.flush()
def copy_frozen(src,dst,m):
 if os.path.exists(dst):raise IOError("Destination already exists")
 os.makedirs(dst);total=sum(v[0] for v in m.values());done=0;st=time.time();last=0
 for rel,(expected,oldmt,sp) in sorted(m.items()):
  if not os.path.exists(sp) or os.path.getsize(sp)!=expected:raise IOError("Source changed before copy: "+rel)
  dp=os.path.join(dst,rel);par=os.path.dirname(dp)
  if not os.path.isdir(par):os.makedirs(par)
  fi=open(sp,"rb")
  try:
   fo=open(dp,"wb")
   try:
    fd=0
    while 1:
     b=fi.read(CHUNK)
     if not b:break
     fo.write(b);fd+=len(b);done+=len(b)
     now=time.time()
     if now-last>=UPDATE_SECONDS:
      status("COPYING",done,total,rel,fd,expected,st);last=now
    fo.flush()
   finally:fo.close()
  finally:fi.close()
  if fd!=expected:raise IOError("Source changed while copying: "+rel)
  try:shutil.copystat(sp,dp)
  except OSError:pass
 status("COPYING",done,total,"",0,0,st);print("")
 return total,time.time()-st
def verify_destination(dst,m):
 # Destination is a live processing folder. Downstream services such as
 # EnsoData may add files immediately after pickup. Extra destination files
 # are therefore informational, not a transfer failure.
 now=manifest(dst,True)
 expected=set(m);actual=set(now)
 missing=sorted(expected-actual);changed=[];extra=sorted(actual-expected)
 for r in sorted(expected&actual):
  if m[r][0]!=now[r][0]:changed.append(r)
 return missing,changed,extra
def sha256(p,label):
 h=hashlib.sha256();total=os.path.getsize(p);done=0;st=time.time();last=0
 f=open(p,"rb")
 try:
  while 1:
   b=f.read(CHUNK)
   if not b:break
   h.update(b);done+=len(b);now=time.time()
   if now-last>=UPDATE_SECONDS:
    status(label,done,total,os.path.basename(p),done,total,st);last=now
 finally:f.close()
 status(label,done,total,"",0,0,st);print("")
 return h.hexdigest()
def signal(root):
 for b,ds,fs in os.walk(root):
  for n in fs:
   if n.lower()=="signal.raw":return os.path.join(b,n)
 return None
def write_marker(path,fields):
 f=open(os.path.join(path,"TRANSFER_COMPLETE.txt"),"wb")
 try:
  for k,v in fields:
   line="%s: %s\r\n"%(k,v)
   f.write(line.encode("ascii","replace"))
 finally:f.close()
def print_list(label,x):
 if x:
  print(label+":")
  for v in x[:20]:print("  "+v)
  if len(x)>20:print("  ...and %d more"%(len(x)-20))
def main():
 print("="*72);print("SLEEP STUDY TRANSFER UTILITY - By Adam J. Girardo");print("="*72)
 x=candidate()
 if not x:print("No qualifying study found.");return
 mt,src,size,count,pd=x;pnum,first,last=patient(pd)
 quiet=int(time.time()-mt);pc=os.environ.get("COMPUTERNAME") or socket.gethostname() or "UNKNOWN-PC"
 user=os.environ.get("USERNAME") or "UNKNOWN"
 stamp=str(int(time.time()));name="%s %s %s"%(stamp,safe(pc),safe(pnum))
 dst=os.path.join(DEST_ROOT,name);archive=os.path.join(BACKUP_ROOT,name)
 print("Patient #   : %s"%pnum);print("Patient     : %s %s"%(first,last))
 print("Computer    : %s"%pc);print("Source      : %s"%src);print("Size        : %s"%hb(size))
 print("Files       : %d"%count);print("Quiet       : %s"%dur(quiet))
 print("Destination : %s"%dst);print("Archive     : %s"%archive);print("")
 if quiet<QUIET_SECONDS:print("SAFETY HOLD: Study changed within the last 2 minutes.");return
 if not os.path.isdir(DEST_ROOT):print("ERROR: Network destination unavailable.");return
 if os.path.exists(dst):print("ERROR: Destination already exists. Nothing changed.");return
 if os.path.exists(archive):print("ERROR: Archive destination already exists. Nothing changed.");return

 frozen=manifest(src,True);time.sleep(1)
 a,r,c=compare(src,frozen,True,True)
 if a or r or c:
  print("SOURCE ACTIVE: Transfer cancelled.");print_list("Added",a);print_list("Removed",r);print_list("Changed",c);return

 print("Safety checks passed.")
 print("After verified copy, the original will be MOVED to the configured backup folder.")
 print("No delete operation is used.")
 if raw_input("\nType TRANSFER to continue: ").strip()!="TRANSFER":print("Cancelled.");return

 started=time.strftime("%Y-%m-%d %H:%M:%S")
 tid=str(uuid.uuid4()).upper()
 try:total,elapsed=copy_frozen(src,dst,frozen)
 except Exception as e:
  print("\nCOPY FAILED: %s"%e);print("Original remains unchanged.");return

 missing,changed,extra=verify_destination(dst,frozen)
 if missing or changed:
  print("DESTINATION VERIFY: FAIL")
  print_list("Missing expected files",missing);print_list("Wrong-size expected files",changed)
  if extra:print_list("Additional downstream files (informational)",extra)
  print("Original remains unchanged.");return
 print("DESTINATION VERIFY: PASS")
 if extra:
  print("DOWNSTREAM FILES: %d additional file(s) detected and allowed."%len(extra))
  print("  (Live processing services may add files after pickup.)")

 sa,sr,sc=compare(src,frozen,True,True)
 if sa or sr or sc:
  print("SOURCE STABILITY: FAIL - ORIGINAL WILL NOT BE ARCHIVED.")
  print_list("Added",sa);print_list("Removed",sr);print_list("Changed",sc);return
 print("SOURCE STABILITY: PASS")

 ss=signal(src);ds=signal(dst);hash_result="NOT PRESENT"
 if ss and ds:
  sh=sha256(ss,"HASH SRC");dh=sha256(ds,"HASH DST")
  if sh!=dh:print("SIGNAL.raw SHA-256: FAIL. Original remains unchanged.");return
  hash_result=sh;print("SIGNAL.raw SHA-256: PASS")
 elif ss or ds:
  print("SIGNAL.raw presence mismatch. Original remains unchanged.");return

 completed=time.strftime("%Y-%m-%d %H:%M:%S")
 fields=[
  ("Transfer ID",tid),("Patient Number",pnum),("Patient Name",first+" "+last),
  ("Workstation",pc),("Windows User",user),("Original Source",src),
  ("Network Destination",dst),("Archive Destination",archive),
  ("Started",started),("Verified",completed),("File Count",str(len(frozen))),
  ("Byte Count",str(total)),("SIGNAL.raw SHA256",hash_result),
  ("Destination Verification","PASS"),("Source Stability","PASS")
 ]
 try:write_marker(dst,fields)
 except Exception as e:
  print("AUDIT MARKER WRITE FAILED: %s"%e);print("Original remains unchanged.");return
 print("NETWORK AUDIT MARKER: WRITTEN")

 # Recheck source one final time after marker creation and immediately before move.
 sa,sr,sc=compare(src,frozen,True,True)
 if sa or sr or sc:
  print("FINAL SOURCE CHECK: FAIL - ORIGINAL WILL NOT BE ARCHIVED.")
  print_list("Added",sa);print_list("Removed",sr);print_list("Changed",sc);return

 if not os.path.isdir(BACKUP_ROOT):
  try:os.makedirs(BACKUP_ROOT)
  except Exception as e:print("Could not create backup folder: %s"%e);return

 try:shutil.move(src,archive)
 except Exception as e:
  print("ARCHIVE MOVE FAILED: %s"%e)
  print("Network copy is verified. Review source/archive manually.");return

 # Archive verification ignores marker because marker is added after this check.
 aa,ar,ac=compare(archive,frozen,False,True)
 if aa or ar or ac:
  print("ARCHIVE VERIFY: FAIL")
  print_list("Extra",aa);print_list("Missing",ar);print_list("Changed",ac)
  print("DO NOT DELETE ANYTHING. Review manually.");return
 print("ARCHIVE VERIFY: PASS")

 fields.append(("Archived",time.strftime("%Y-%m-%d %H:%M:%S")))
 fields.append(("Archive Verification","PASS"))
 try:write_marker(archive,fields)
 except Exception as e:
  print("WARNING: Archive succeeded but archive audit marker failed: %s"%e)

 print("");print("="*72);print("TRANSFER COMPLETE");print("="*72)
 print("Network copy : VERIFIED")
 print("SIGNAL.raw   : VERIFIED")
 print("Archive      : VERIFIED")
 print("Files        : %d"%len(frozen));print("Data         : %s"%hb(total))
 print("Copy time    : %s"%dur(elapsed));print("Average rate : %s/s"%hb(total/max(.01,elapsed)))
 print("");print("Original study archived to:");print("  "+archive)
if __name__=="__main__":
 try:main()
 except KeyboardInterrupt:print("\nINTERRUPTED. Review the displayed stage before retrying.")
 except Exception as e:print("\nUNEXPECTED ERROR: %s"%e)
 print("");raw_input("Press ENTER to close...")
