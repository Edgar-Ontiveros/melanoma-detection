# deploy/

Archivos que se copian tal cual a la instancia (`/opt/melanoma`): `docker-compose.yml`,
`Caddyfile` e `install.sh`. El procedimiento completo, el costo y el apagado están en
`docs/DEPLOY.md`; los objetivos `make deploy-install`, `make deploy`, `make deploy-logs`,
`make deploy-stop` y `make deploy-start` los usan desde la laptop por SSH.
