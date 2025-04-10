# Dependency Management for Kave Project

This project uses pip-tools to manage Python dependencies in a structured and reproducible way. This approach is optimized for FastAPI applications deployed to Heroku.

## Directory Structure

- `requirements/base.in`: Core direct dependencies for the application
- `requirements/integrations.in`: Additional dependencies for integrations (includes base.in)
- `requirements/dev.in`: Development and testing dependencies (includes integrations.in)
- `requirements/base.txt`: Compiled dependencies from base.in (pinned versions)
- `requirements/integrations.txt`: Compiled dependencies from integrations.in
- `requirements/dev.txt`: Compiled dependencies from dev.in
- `requirements.txt`: Root file that points to integrations.txt (for Heroku deployment)

## How to Use

### Adding New Dependencies

1. Add new dependencies to the appropriate `.in` file:
   - Production application dependencies -> `requirements/base.in`
   - Integration-specific dependencies -> `requirements/integrations.in`
   - Development/testing dependencies -> `requirements/dev.in`

2. **Never** modify `.txt` files directly.

### Compiling Requirements

After modifying any `.in` file, compile the corresponding `.txt` file:

```bash
# Compile base dependencies
pip-compile requirements/base.in --output-file=requirements/base.txt

# Compile integration dependencies
pip-compile requirements/integrations.in --output-file=requirements/integrations.txt

# Compile development dependencies 
pip-compile requirements/dev.in --output-file=requirements/dev.txt
```

### Installing Dependencies

- For development: `pip install -r requirements/dev.txt`
- For production: `pip install -r requirements/integrations.txt` (or simply `pip install -r requirements.txt`)

### Updating Dependencies

To update all dependencies to their latest versions within the specified constraints:

```bash
pip-compile --upgrade requirements/base.in --output-file=requirements/base.txt
pip-compile --upgrade requirements/integrations.in --output-file=requirements/integrations.txt
pip-compile --upgrade requirements/dev.in --output-file=requirements/dev.txt
```

## Heroku Deployment

The root `requirements.txt` file points to `requirements/integrations.txt`, which is what Heroku uses during the build process. This ensures that:

1. Only production dependencies are installed in the Heroku environment
2. All dependencies have pinned versions for reproducible builds
3. The deployment is as efficient as possible

This setup aligns with Heroku's best practices for Python applications. 