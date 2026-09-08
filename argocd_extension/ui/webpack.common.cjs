const path = require("path");

/** @type {import('webpack').Configuration} */
module.exports = {
  context: path.resolve(__dirname),
  resolve: {
    extensions: [".tsx", ".ts", ".js"],
  },
  module: {
    rules: [
      {
        test: /\.tsx?$/,
        loader: "ts-loader",
        options: { transpileOnly: true },
        exclude: /node_modules/,
      },
    ],
  },
  stats: "errors-warnings",
};
