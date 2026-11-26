FROM composer:2.10.2
RUN install-php-extensions gd
COPY --chmod=755 test-composer.sh /usr/local/bin/test-composer
ENTRYPOINT ["/usr/local/bin/test-composer"]
