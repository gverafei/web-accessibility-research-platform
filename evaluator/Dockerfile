FROM node:20-bookworm

WORKDIR /evaluator

RUN apt-get update && apt-get install -y \
    chromium \
    && rm -rf /var/lib/apt/lists/*

COPY package.json /evaluator/package.json
RUN npm install

COPY . /evaluator/

EXPOSE 3000

CMD ["node", "server.js"]
