FROM node:18-alpine

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json ./
RUN npm install

# Copy application source code
COPY . .

# Expose port 3000 for the React development server
EXPOSE 3000

# Start the application exactly like local development
CMD ["npm", "start"]
