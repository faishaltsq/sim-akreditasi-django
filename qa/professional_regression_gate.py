"""Final source-attributed regression gate for the isolated workspace."""
import os,sys,json,hashlib,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
assert root.name=='arima-igd-professional-care-isolated'
evidence=root/'docs/superpowers/evidence/igd-professional-care';evidence.mkdir(parents=True,exist_ok=True)
roots=('accounts','akreditasi','config','klinis','pasien','sdm','templates','static')
def snapshot():
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for directory in roots for p in sorted((root/directory).rglob('*')) if p.is_file() and p.suffix in {'.py','.html','.js','.css'} and '__pycache__' not in p.parts and p.name not in {'professional_browser_settings.py','professional_qa_settings.py'}}
before=snapshot()
venv=root.parent/'sim-akreditasi-django/.venv/Scripts/python.exe'
env=dict(os.environ,DATABASE_URL='',DJANGO_DEBUG='true',PYTHONIOENCODING='utf-8')
log=Path(os.environ['TMPDIR'])/'professional-full-final.log'
with log.open('w',encoding='utf-8') as output:
    result=subprocess.run([str(venv),'manage.py','test','pasien','klinis','accounts','sdm.tests.test_clinical_access','--keepdb','--noinput'],cwd=root,env=env,stdout=output,stderr=subprocess.STDOUT)
after=snapshot()
changed=sorted(p for p in before.keys()|after.keys() if before.get(p)!=after.get(p))
manifest={'exit_code':result.returncode,'changed_during_run':changed,'source_files':len(before),'source_hashes':before,'log':str(log)}
(evidence/'full-regression-source.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps({'exit_code':result.returncode,'changed_during_run':changed,'source_files':len(before)}))
raise SystemExit(result.returncode or bool(changed))
