FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

ARG VITE_API_BASE_URL=/api
ARG VITE_DEV_MOCKS=false
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_DEV_MOCKS=${VITE_DEV_MOCKS}

RUN npm run build

FROM nginx:alpine AS serve

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
