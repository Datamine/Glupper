# ArchiveBox Integration for Glupper

This document describes how to set up and configure ArchiveBox for use with Glupper, which automatically archives URLs from posts.

## What is ArchiveBox?

ArchiveBox is an open-source self-hosted web archiving tool. It captures and saves web pages, allowing you to create your own offline archive of the web. When users post URLs on Glupper, ArchiveBox automatically captures these web pages to ensure they remain accessible even if the original site goes down.

## Setting Up ArchiveBox

### 1. Install ArchiveBox

The easiest way to run ArchiveBox is using Docker:

```bash
# Create a directory for ArchiveBox data
mkdir -p ~/archivebox/data

# Run ArchiveBox with Docker
docker run -d --name archivebox \
  -e ADMIN_USERNAME=admin \
  -e ADMIN_PASSWORD=yourpassword \
  -p 8000:8000 \
  -v ~/archivebox/data:/data \
  archivebox/archivebox server 0.0.0.0:8000
```

For other installation methods, see the [official documentation](https://github.com/ArchiveBox/ArchiveBox#quickstart).

### 2. Configure ArchiveBox

1. Access the ArchiveBox admin interface at `http://localhost:8000/admin/`
2. Log in with the username and password you set up
3. Configure the archiving methods in Settings
4. If needed, create an API token for authentication

### 3. Update Glupper Configuration

Update your Glupper `config_secrets.py` file with the correct ArchiveBox API endpoint:

```python
ARCHIVEBOX_API_ENDPOINT = "http://localhost:8000/api/archive/"
ARCHIVEBOX_TIMEOUT = 30.0  # seconds
```

If your ArchiveBox instance requires authentication, update the API call in `src/services/archive_service.py`.

## Additional Configuration Options

### Storage Requirements

ArchiveBox can use significant disk space depending on your archiving settings. Consider these guidelines:

- A single webpage might use 1-50MB of storage with all archiving methods enabled
- URLs with video content can take up much more space
- Consider setting up storage monitoring

### Performance Considerations

- ArchiveBox can be resource-intensive when archiving many pages
- Consider running it on a separate server for high-traffic instances
- Adjust the timeout in `config_secrets.py` if needed for large pages

### Security Notes

- ArchiveBox will execute JavaScript from archived pages if you're using Chrome/Chromium archiving
- Consider running ArchiveBox in a separate network segment if security is a concern
- Do not expose the ArchiveBox admin interface to the public internet without proper security measures

## Troubleshooting

If URLs are not being archived properly:

1. Check the Glupper logs for errors
2. Verify that ArchiveBox is running and accessible
3. Inspect the ArchiveBox archive logs for specific URL failures
4. Ensure ArchiveBox has the necessary dependencies for your chosen archiving methods

## References

- [ArchiveBox Documentation](https://github.com/ArchiveBox/ArchiveBox/wiki)
- [ArchiveBox API Documentation](https://github.com/ArchiveBox/ArchiveBox/wiki/API-Reference)