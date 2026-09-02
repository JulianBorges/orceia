import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const maxDuration = 300; // Garantir que a Vercel não corte o stream precocemente

export async function GET(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  return handleProxy(request, params.path);
}

export async function POST(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  return handleProxy(request, params.path);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  return handleProxy(request, params.path);
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  return handleProxy(request, params.path);
}

export async function PUT(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  return handleProxy(request, params.path);
}

async function handleProxy(request: NextRequest, pathArray: string[]) {
  const path = pathArray.join("/");
  const backendUrl = process.env.BACKEND_API_URL || "http://127.0.0.1:8000";
  const apiUrl = `${backendUrl}/${path}`;

  try {
    const apiSecret = process.env.API_SECRET_KEY;
    if (!apiSecret) {
      console.error("[Proxy] ERRO CRÍTICO: API_SECRET_KEY não configurada no ambiente.");
      return NextResponse.json({ error: "Configuração de servidor inválida" }, { status: 500 });
    }

    const headers = new Headers(request.headers);
    headers.set("x-api-secret", apiSecret);
    
    // Repassa o x-tenant-id injetado pelo middleware, se existir. 
    // Como o usuário não consegue falsificar cookies assinados/HttpOnly facilmente no middleware,
    // o Backend pode confiar plenamente neste Header
    const tenantId = request.headers.get("x-tenant-id");
    if (tenantId) {
        headers.set("x-tenant-id", tenantId);
    }
    
    headers.delete("host"); 
    
    let body = undefined;
    if (request.method !== "GET" && request.method !== "HEAD") {
      body = await request.arrayBuffer();
    }

    const response = await fetch(apiUrl, {
      method: request.method,
      headers: headers,
      body: body,
      redirect: "manual",
    });

    const responseHeaders = new Headers(response.headers);
    
    // Tratamento rigoroso para SSE (Server-Sent Events) evitando Buffering do Next.js
    if (responseHeaders.get("content-type")?.includes("text/event-stream") && response.body) {
        responseHeaders.set("Cache-Control", "no-cache, no-transform");
        responseHeaders.set("Connection", "keep-alive");
        responseHeaders.set("X-Accel-Buffering", "no");

        // Cria um pipeline de transporte ativo (força o flush de cada chunk)
        const reader = response.body.getReader();
        const stream = new ReadableStream({
            async start(controller) {
                try {
                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;
                        controller.enqueue(value);
                    }
                } catch (e) {
                    console.error("Erro no stream proxy:", e);
                } finally {
                    controller.close();
                }
            },
            cancel() {
                reader.cancel();
            }
        });

        return new NextResponse(stream, {
            status: response.status,
            headers: responseHeaders
        });
    }

    return new NextResponse(response.body, {
      status: response.status,
      headers: responseHeaders,
    });
  } catch (error) {
    console.error("Proxy Error:", error);
    return NextResponse.json(
      { error: "Erro interno no Proxy de Comunicação Edge" },
      { status: 500 }
    );
  }
}
