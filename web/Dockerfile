FROM nginxinc/nginx-unprivileged:1.31.7-alpine

COPY --chown=101:101 default.conf /etc/nginx/conf.d/default.conf
COPY --chown=101:101 index.html /usr/share/nginx/html/index.html
USER 101:101
EXPOSE 8080
