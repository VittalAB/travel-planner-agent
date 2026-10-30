import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { createLibrary, defineComponent, Renderer } from "@openuidev/react-lang";
import { z } from "zod/v4";

const AssistantText = defineComponent({
  name: "AssistantText",
  description: "Renders the travel assistant's markdown response.",
  props: z.object({
    content: z.string().describe("Markdown response text"),
  }),
  component: ({ props }) => (
    <div className="assistant-markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{props.content}</ReactMarkdown>
    </div>
  ),
});

const messageLibrary = createLibrary({
  components: [AssistantText],
  root: "AssistantText",
});

export function AssistantMessage({ content, isStreaming }) {
  const response = `root = AssistantText(${JSON.stringify(content)})`;

  return (
    <Renderer
      response={response}
      library={messageLibrary}
      isStreaming={isStreaming}
      onError={(errors) => {
        console.error("OpenUI response rendering failed", errors);
      }}
    />
  );
}
