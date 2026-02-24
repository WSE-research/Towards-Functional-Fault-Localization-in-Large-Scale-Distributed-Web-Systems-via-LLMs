# A helper script to bypass several issues coming up when using it with actual projects

#!/bin/sh
set -e

##### Configuration #####
# Mitigate glibc init error in old JDKs when RLIMIT_NOFILE is unlimited or too low
# "library initialization failed - unable to allocate file descriptor table - out of memory"
n=$(ulimit -n 2>/dev/null || echo 1024)
case "$n" in
  unlimited)
    # Set to a sane finite value
    ulimit -n 65536 || true
    ;;
  *)
    # Cap absurdly large values (some docker runtimes set ~1e9)
    if echo "$n" | grep -Eq '^[0-9]+$'; then
      if [ "$n" -gt 1048576 ] 2>/dev/null; then
        for val in 65536 32768 16384 8192 4096 2048 1024; do
          if ulimit -n "$val" 2>/dev/null; then
            break
          fi
        done
      elif [ "$n" -lt 1024 ] 2>/dev/null; then
        # If extremely low (e.g., 0), raise it (best effort)
        for val in 4096 2048 1024; do
          if ulimit -n "$val" 2>/dev/null; then
            break
          fi
        done
      fi
    fi
    ;;
esac

# Also cap number of processes to something reasonable to avoid pathological defaults
ulimit -u 4096 2>/dev/null || true

# Exec the provided command
exec "$@"

### Entrypoint ###

# Do whatever you like
