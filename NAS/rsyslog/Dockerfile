# Fichier: Dockerfile
# Emplacement: Project_homeserver/nas/rsyslog/Dockerfile
# Langage: Dockerfile
# Role: construit l'image du conteneur rsyslog qui recevra et harmonisera tous les logs.

FROM alpine:3.20

RUN apk add --no-cache rsyslog

COPY 60-harmonisation.conf /etc/rsyslog.d/60-harmonisation.conf

RUN mkdir -p /var/log/harmonise

EXPOSE 1514/udp

CMD ["rsyslogd", "-n"]
