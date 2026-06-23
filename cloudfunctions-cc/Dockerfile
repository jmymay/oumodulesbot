FROM stemclubmodulesbot/cloudfunctions-cc-base:latest AS build

COPY . /v/source
RUN curl https://raw.githubusercontent.com/jmymay/oumodulesbot/main/oumodulesbot/cache.json -o /v/source/cache.json
WORKDIR /v/source

# Compile the binary and strip it to reduce its size.
RUN cmake --build /v/binary
RUN strip /v/binary/interaction

# Run tests
RUN /v/binary/interaction_lib_test && /v/binary/verify_ed25519_test

# Create the final deployment image, using `scratch` (the empty Docker image)
# as the starting point. Effectively we create an image that only contains
# our program.
FROM scratch AS cloud-run-hello
WORKDIR /r

# Copy the program from the previously created stage and the shared libraries it
# depends on.
COPY --from=build /v/binary/interaction /r
COPY --from=build /v/binary/roots.pem /usr/share/grpc/roots.pem
COPY --from=build /v/source/cache.json /r
COPY --from=build /lib/ld-musl-x86_64.so.1 /lib/ld-musl-x86_64.so.1
COPY --from=build /usr/lib/libstdc++.so.6 /usr/lib/libstdc++.so.6
COPY --from=build /usr/lib/libgcc_s.so.1 /usr/lib/libgcc_s.so.1

# Make the program the entry point.
ENTRYPOINT [ "/r/interaction" ]
