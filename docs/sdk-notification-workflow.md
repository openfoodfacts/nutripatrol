# SDK API Change Notification Workflow

This workflow automatically creates issues in OpenFoodFacts SDK repositories when a NutriPatrol release contains API changes.

## How it works

1. **Trigger**: The workflow runs when a new release is published in the NutriPatrol repository.

2. **API Change Detection**: The workflow analyzes the release notes for API-related keywords:
   - `api`
   - `endpoint`
   - `route`
   - `breaking.*change`
   - `backward.*incompatible`

3. **Issue Creation**: If API changes are detected, the workflow creates issues in all OpenFoodFacts SDK repositories:
   - openfoodfacts-php
   - openfoodfacts-js
   - openfoodfacts-laravel
   - openfoodfacts-python
   - openfoodfacts-ruby
   - openfoodfacts-java
   - openfoodfacts-elixir
   - openfoodfacts-dart
   - openfoodfacts-go

## Issue Template

Each created issue includes:
- Release information (name, tag, URL)
- Full release notes
- Checklist of action items for SDK maintainers
- Useful links (API docs, release notes, repository)
- Automatic labels: `enhancement`, `api-update`

## Configuration

The workflow uses the `GITHUB_TOKEN` secret (automatically provided by GitHub) to create issues in the SDK repositories.

## File Location

`.github/workflows/notify-sdk-api-changes.yml`

## Testing

The API detection logic has been tested with real examples from the NutriPatrol changelog:
- ✅ Detects: "add /api/v1 prefix to all API routes"
- ✅ Detects: "Add new routes and features for ticket and flag management (CRUD api)"
- ✅ Ignores: "fix container-deploy.yml config"
- ✅ Ignores: "add new commands to Makefile"