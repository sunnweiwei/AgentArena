# Migration to .env - Notes

## Summary

All sensitive credentials have been moved to `.env` files. The old `key` and `openaikey` files are still supported for backward compatibility but should be migrated.

## What Changed

### Files Updated
- ✅ `COMMANDS.md` - Now uses `source load_env.sh` instead of `cat key`
- ✅ `deploy.py` - Now uses `python-dotenv` to load from `.env`
- ✅ `test_openai_latency.py` - Now loads from `.env` with fallback to `openaikey`
- ✅ `debug_stream.py` - Now loads from `.env` with fallback to `openaikey`
- ✅ `run_services.sh` - Now uses `load_env_for_expect.sh`
- ✅ `deploy.sh` - Now loads from `.env`
- ✅ `.gitignore` - Added `key`, `openaikey`, and stricter `.env` patterns
- ✅ `backend/requirements.txt` - Added `python-dotenv`

### New Files
- ✅ `.env.example` - Template file (safe to commit)
- ✅ `load_env.sh` - Bash helper to load `.env`
- ✅ `load_env_for_expect.sh` - Helper for expect scripts
- ✅ `setup_env.sh` - Migration script
- ✅ `ENV_SETUP.md` - Setup documentation

## Migration Steps

1. **Run the setup script:**
   ```bash
   ./setup_env.sh
   ```
   This will automatically create `.env` from existing `key` and `openaikey` files.

2. **Verify it works:**
   ```bash
   source load_env.sh
   echo "SSH password loaded: ${SSH_PASSWORD:0:3}..."
   echo "OpenAI key loaded: ${OPENAI_API_KEY:0:7}..."
   ```

3. **Test a command:**
   ```bash
   source load_env.sh
   export PASSWORD=$SSH_PASSWORD
   # Try a simple command from COMMANDS.md
   ```

4. **Optional: Remove old files** (after verifying everything works):
   ```bash
   rm key openaikey
   ```

## Backward Compatibility

All scripts maintain backward compatibility:
- If `.env` exists, it's used
- If `.env` doesn't exist but `key`/`openaikey` exist, those are used
- Error messages guide users to create `.env` if neither exists

## Scripts Still Using Legacy Format

The following scripts still use `cat key` but will work with the fallback:
- `setup_server_final.sh`
- `setup_npm.sh`
- `deploy_simple.sh`
- `setup_server.sh`
- `deploy_streaming.sh`
- And many others in the project

These can be updated gradually or will continue to work with the `key` file fallback.

## Security Improvements

- ✅ `.env` is in `.gitignore` (won't be committed)
- ✅ `key` and `openaikey` are now in `.gitignore`
- ✅ `.env.example` is safe to commit (template only)
- ✅ All scripts check for `.env` first before falling back

## Next Steps

1. Run `./setup_env.sh` to create your `.env` file
2. Test that commands work with the new setup
3. Update any custom scripts you have to use `load_env.sh`
4. Consider removing old `key` and `openaikey` files after verification

