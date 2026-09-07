const path = require("path");
const { merge } = require("webpack-merge");
const CopyWebpackPlugin = require("copy-webpack-plugin");
const MiniCssExtractPlugin = require("mini-css-extract-plugin");
const common = require("./webpack.common.cjs");

const faRoot = path.resolve(__dirname, "node_modules/@fortawesome/fontawesome-free");

/** @type {import('webpack').Configuration} */
module.exports = merge(common, {
  mode: "production",
  entry: "./src/entries/standalone.tsx",
  output: {
    path: path.resolve(__dirname, "dist/standalone"),
    filename: "app.js",
    iife: true,
    globalObject: "globalThis",
  },
  module: {
    rules: [
      {
        test: /\.css$/,
        use: [MiniCssExtractPlugin.loader, "css-loader"],
      },
    ],
  },
  optimization: {
    splitChunks: false,
    runtimeChunk: false,
  },
  plugins: [
    new MiniCssExtractPlugin({ filename: "styles.css" }),
    new CopyWebpackPlugin({
      patterns: [
        { from: "standalone.html", to: "index.html" },
        { from: "favicon.svg", to: "favicon.svg" },
        { from: path.join(faRoot, "css/fontawesome.min.css"), to: "fontawesome/css/fontawesome.min.css" },
        { from: path.join(faRoot, "css/solid.min.css"), to: "fontawesome/css/solid.min.css" },
        { from: path.join(faRoot, "webfonts/fa-solid-900.woff2"), to: "fontawesome/webfonts/fa-solid-900.woff2" },
        { from: path.join(faRoot, "webfonts/fa-solid-900.ttf"), to: "fontawesome/webfonts/fa-solid-900.ttf" },
        { from: path.join(faRoot, "LICENSE.txt"), to: "fontawesome/LICENSE.txt" },
      ],
    }),
  ],
});
