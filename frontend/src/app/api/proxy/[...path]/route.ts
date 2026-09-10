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
  const searchParams = request.nextUrl.search; // includes the '?' prefix if there are params
  const apiUrl = `${backendUrl}/${path}${searchParams}`;

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
    
    // Remove Accept-Encoding ANTES de chamar o Cloud Run.
    // CRÍTICO para redes governamentais: se o Cloud Run receber Accept-Encoding: gzip,
    // ele comprime a resposta SSE. O proxy corporativo (Fortinet/Squid) então bufferiza
    // toda a stream aguardando o fim do gzip antes de liberar — resultando em 0 bytes no browser.
    headers.delete("accept-encoding");
    headers.delete("accept-encoding".toLowerCase());
    
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
    
    // Tratamento rigoroso para SSE (Server-Sent Events) evitando Buffering
    if (responseHeaders.get("content-type")?.includes("text/event-stream") && response.body) {
        responseHeaders.set("Cache-Control", "no-cache, no-transform");
        responseHeaders.set("Connection", "keep-alive");
        responseHeaders.set("X-Accel-Buffering", "no");
        // Identity = sem compressão: instrui qualquer proxy intermediário a não bufferizar
        // aguardando o fim do gzip. Sem isso, proxies corporativos retornam 0 bytes ao browser.
        responseHeaders.set("Content-Encoding", "identity");
        responseHeaders.delete("content-length"); // SSE não tem content-length

        // Usa Response nativo (não NextResponse) para passthrough direto do body do Cloud Run.
        // NextResponse pode adicionar camadas de processamento que bufferizam o stream.
        return new Response(response.body, {
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
