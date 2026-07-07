const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

function runCommand(sql) {
  // Use -w to disable password prompting entirely
  // Remove the "echo" pipe, it's causing the conflict
  const cmd = `psql -v ON_ERROR_STOP=1 --set=VERBOSITY=default -w -h ${process.env.POSTGRES_HOST} -U ${process.env.POSTGRES_USER} -d postgres`;
  
  return execSync(cmd, { 
    input: sql,
    env: { 
      ...process.env, 
      PGPASSWORD: process.env.POSTGRES_PASSWORD 
    },
    stdio: 'inherit'
  });
}

function runMigrations() {
  const files = fs.readdirSync(__dirname).filter(f => f.endsWith('.sql')).sort();
  
  for (const file of files) {
    let sql = fs.readFileSync(path.join(__dirname, file), 'utf8');
    sql = sql.replace(/\${(\w+)}/g, (_, key) => process.env[key] || '');
    
    console.log(`--- Executing ${file} ---`);
    runCommand(sql);
  }
}

// No waiting required!
runMigrations();