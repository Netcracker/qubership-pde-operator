# docker build -t pde-argo-extension-backend:dev -f argocd_extension/backend/Dockerfile argocd_extension/backend

FROM golang:1.27-alpine AS build
WORKDIR /src
COPY go.mod ./
COPY main.go ./
RUN go build -o /pde-argo-extension-backend .

FROM alpine:3.24
RUN apk upgrade --no-cache && apk add --no-cache ca-certificates
COPY --from=build /pde-argo-extension-backend /usr/local/bin/pde-argo-extension-backend
USER 65534:65534
EXPOSE 8081
ENTRYPOINT ["pde-argo-extension-backend"]
