FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package*.json ./
RUN --mount=type=secret,id=cloud_ca,target=/run/secrets/cloud_ca,required=false if [ -f /run/secrets/cloud_ca ]; then NODE_EXTRA_CA_CERTS=/run/secrets/cloud_ca npm ci; else npm ci; fi
COPY frontend .
ARG NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
ENV NEXT_PUBLIC_BACKEND_URL=$NEXT_PUBLIC_BACKEND_URL
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build
FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
COPY --from=build --chown=node:node /app ./
USER node
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s CMD node -e "fetch('http://127.0.0.1:3000').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"
CMD ["npm","start"]
