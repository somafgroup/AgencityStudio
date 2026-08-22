# Security policy

Please report suspected security vulnerabilities privately to the maintainers or through GitHub private vulnerability reporting when it is enabled for the repository. Do not open a public issue containing exploit details, credentials, personal data or other sensitive material.

## Scope

Security reports may cover the Django application, authentication/authorization as those features are introduced, dependency vulnerabilities, container configuration, unsafe file handling, cross-site scripting, CSRF, secret exposure, worker/job isolation and other deployment risks.

Scientific disagreements or unexpected AgencityLab numerical results are not security vulnerabilities; report those through the appropriate scientific/software issue channel without sensitive data.

## Deployment expectations

Production deployments must use `config.settings.production`, a strong unique `DJANGO_SECRET_KEY`, explicit allowed hosts, HTTPS, secure cookies and appropriate proxy/HSTS settings. `.env.example` contains development-only values and must not be used as production credentials.

Operational endpoints expose only non-sensitive service/dependency state. Do not extend them with credentials, database URLs, stack traces or other secrets.
