import type { Metadata } from "next";
import Link from "next/link";
import { LogoMark } from "@/components/Logo";

export const metadata: Metadata = {
  title: "Política de Privacidade — feedeo",
  description:
    "Saiba como a feedeo coleta, usa, armazena e protege seus dados pessoais, em conformidade com a LGPD.",
};

const UPDATED_AT = "22 de julho de 2026";
const CONTACT_EMAIL = "thiago@feedeo.com.br";

export default function PrivacidadePage() {
  return (
    <div className="hero-glow min-h-[80vh] px-4 pb-20 pt-10 sm:px-6">
      <article className="mx-auto max-w-3xl">
        <div className="mb-10 flex flex-col items-start gap-4">
          <Link href="/" className="flex items-center gap-2.5 opacity-80 transition hover:opacity-100">
            <LogoMark size={28} />
            <span className="text-[15px] font-semibold tracking-tight">
              feed<span className="text-gradient">eo</span>
            </span>
          </Link>
          <div>
            <p className="text-[12px] font-medium uppercase tracking-[0.14em] text-white/35">
              Documento legal
            </p>
            <h1 className="mt-2 text-[28px] font-semibold tracking-tight sm:text-[34px]">
              Política de Privacidade
            </h1>
            <p className="mt-2 text-[13px] text-white/40">
              Última atualização: {UPDATED_AT}
            </p>
          </div>
        </div>

        <div className="glass space-y-8 rounded-3xl p-6 text-[14px] leading-relaxed text-white/70 sm:p-10 sm:text-[15px]">
          <section className="space-y-3">
            <h2 className="text-[17px] font-semibold text-white">1. Quem somos</h2>
            <p>
              A <strong className="text-white/90">feedeo</strong> (&quot;nós&quot;, &quot;nosso&quot; ou
              &quot;plataforma&quot;), disponível em{" "}
              <a href="https://feedeo.com.br" className="text-[#c084fc] hover:underline">
                feedeo.com.br
              </a>
              , é uma plataforma de geração de vídeos e conteúdos para redes sociais com auxílio de
              inteligência artificial. Esta Política de Privacidade descreve como coletamos, usamos,
              armazenamos, compartilhamos e protegemos seus dados pessoais, em conformidade com a
              Lei Geral de Proteção de Dados (Lei nº 13.709/2018 — LGPD) e demais normas aplicáveis.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-[17px] font-semibold text-white">2. Dados que coletamos</h2>
            <p>Podemos tratar as seguintes categorias de dados:</p>
            <ul className="list-disc space-y-2 pl-5 marker:text-white/30">
              <li>
                <strong className="text-white/85">Dados de conta:</strong> nome, e-mail e senha
                (armazenada de forma criptografada/hash).
              </li>
              <li>
                <strong className="text-white/85">Dados de uso e conteúdo:</strong> temas, roteiros,
                narrações, imagens, vídeos, workspaces, identidades de marca e demais conteúdos que
                você cria ou envia na plataforma.
              </li>
              <li>
                <strong className="text-white/85">Dados de pagamento:</strong> informações de
                assinatura e cobrança processadas por provedores de pagamento (como Stripe). Nós não
                armazenamos o número completo do cartão.
              </li>
              <li>
                <strong className="text-white/85">Dados de integração:</strong> tokens e identificadores
                necessários para conectar contas de redes sociais (ex.: Instagram), quando você
                autorizar.
              </li>
              <li>
                <strong className="text-white/85">Dados técnicos:</strong> endereço IP, tipo de
                dispositivo/navegador, logs de acesso e diagnósticos necessários para segurança e
                funcionamento do serviço.
              </li>
            </ul>
          </section>

          <section className="space-y-3">
            <h2 className="text-[17px] font-semibold text-white">3. Finalidades do tratamento</h2>
            <p>Utilizamos seus dados para:</p>
            <ul className="list-disc space-y-2 pl-5 marker:text-white/30">
              <li>criar e gerenciar sua conta;</li>
              <li>gerar roteiros, narrações, planos visuais, imagens e vídeos sob sua solicitação;</li>
              <li>processar assinaturas, cobranças e suporte ao cliente;</li>
              <li>publicar ou agendar conteúdos nas plataformas que você conectar;</li>
              <li>melhorar a estabilidade, segurança e desempenho do produto;</li>
              <li>cumprir obrigações legais e regulatórias;</li>
              <li>comunicar atualizações importantes do serviço (ex.: mudanças nesta política).</li>
            </ul>
          </section>

          <section className="space-y-3">
            <h2 className="text-[17px] font-semibold text-white">4. Bases legais (LGPD)</h2>
            <p>O tratamento ocorre com base, conforme o caso, em:</p>
            <ul className="list-disc space-y-2 pl-5 marker:text-white/30">
              <li>
                <strong className="text-white/85">execução de contrato</strong> (prestação do serviço
                contratado);
              </li>
              <li>
                <strong className="text-white/85">consentimento</strong> (quando exigido, como em
                determinadas integrações ou comunicações);
              </li>
              <li>
                <strong className="text-white/85">cumprimento de obrigação legal</strong>;
              </li>
              <li>
                <strong className="text-white/85">legítimo interesse</strong>, quando aplicável e
                respeitando seus direitos e liberdades fundamentais (ex.: segurança e prevenção a
                fraudes).
              </li>
            </ul>
          </section>

          <section className="space-y-3">
            <h2 className="text-[17px] font-semibold text-white">5. Compartilhamento com terceiros</h2>
            <p>
              Para operar a plataforma, podemos compartilhar dados com prestadores de serviço que
              atuam como operadores ou parceiros necessários ao funcionamento, incluindo:
            </p>
            <ul className="list-disc space-y-2 pl-5 marker:text-white/30">
              <li>provedores de IA e mídia (ex.: OpenAI, ElevenLabs, fal.ai);</li>
              <li>provedores de pagamento (ex.: Stripe);</li>
              <li>plataformas sociais que você conectar (ex.: Meta/Instagram);</li>
              <li>infraestrutura de hospedagem, armazenamento e monitoramento.</li>
            </ul>
            <p>
              Esses terceiros recebem apenas os dados necessários para executar suas funções e devem
              tratá-los conforme a legislação aplicável e contratos de confidencialidade/proteção de
              dados. Não vendemos seus dados pessoais.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-[17px] font-semibold text-white">6. Transferência internacional</h2>
            <p>
              Alguns provedores podem processar dados fora do Brasil. Nesses casos, adotamos
              salvaguardas compatíveis com a LGPD, como cláusulas contratuais e escolha de fornecedores
              com padrões adequados de segurança.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-[17px] font-semibold text-white">7. Cookies e tecnologias similares</h2>
            <p>
              Podemos usar cookies e armazenamento local essenciais para autenticação, sessão e
              preferências. Cookies não essenciais, se forem usados no futuro, serão tratados com as
              bases legais e mecanismos de consentimento cabíveis.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-[17px] font-semibold text-white">8. Armazenamento e retenção</h2>
            <p>
              Mantemos seus dados pelo tempo necessário para prestar o serviço, cumprir obrigações
              legais, resolver disputas e fazer valer acordos. Conteúdos gerados e arquivos de mídia
              podem permanecer associados à sua conta enquanto ela estiver ativa. Após exclusão da
              conta, eliminamos ou anonimizamos os dados pessoais, salvo hipóteses legais de retenção.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-[17px] font-semibold text-white">9. Segurança</h2>
            <p>
              Adotamos medidas técnicas e administrativas razoáveis para proteger seus dados, como
              criptografia em trânsito (HTTPS), controle de acesso, hashing de senhas e monitoramento.
              Nenhum sistema é 100% seguro; caso identifique um incidente, entre em contato conosco.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-[17px] font-semibold text-white">10. Seus direitos</h2>
            <p>Nos termos da LGPD, você pode solicitar:</p>
            <ul className="list-disc space-y-2 pl-5 marker:text-white/30">
              <li>confirmação da existência de tratamento;</li>
              <li>acesso, correção e atualização dos dados;</li>
              <li>anonimização, bloqueio ou eliminação de dados desnecessários;</li>
              <li>portabilidade, quando aplicável;</li>
              <li>informação sobre compartilhamentos;</li>
              <li>revogação do consentimento, quando essa for a base legal;</li>
              <li>oposição a tratamentos em hipóteses legais cabíveis.</li>
            </ul>
            <p>
              Para exercer esses direitos, envie um e-mail para{" "}
              <a href={`mailto:${CONTACT_EMAIL}`} className="text-[#c084fc] hover:underline">
                {CONTACT_EMAIL}
              </a>
              . Também é possível apresentar reclamação à Autoridade Nacional de Proteção de Dados
              (ANPD).
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-[17px] font-semibold text-white">11. Conteúdo gerado e responsabilidade</h2>
            <p>
              Você é responsável pelo conteúdo que solicita, envia e publica por meio da feedeo,
              incluindo respeito a direitos autorais, marcas, imagem de terceiros e políticas das
              plataformas sociais. Não use o serviço para gerar ou disseminar conteúdo ilegal,
              discriminatório, enganoso ou que viole direitos de terceiros.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-[17px] font-semibold text-white">12. Menores de idade</h2>
            <p>
              O serviço é destinado a pessoas com capacidade legal para contratar. Não coletamos
              intencionalmente dados de menores de 18 anos sem o consentimento adequado do
              responsável legal. Se identificar cadastro indevido, contate-nos para remoção.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-[17px] font-semibold text-white">13. Alterações desta política</h2>
            <p>
              Podemos atualizar esta Política de Privacidade periodicamente. A versão vigente estará
              sempre disponível nesta página, com a data da última atualização. Mudanças relevantes
              poderão ser comunicadas por e-mail ou aviso na plataforma.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-[17px] font-semibold text-white">14. Contato</h2>
            <p>
              Dúvidas sobre privacidade ou pedidos relacionados aos seus dados pessoais:
            </p>
            <p>
              E-mail:{" "}
              <a href={`mailto:${CONTACT_EMAIL}`} className="text-[#c084fc] hover:underline">
                {CONTACT_EMAIL}
              </a>
              <br />
              Site:{" "}
              <a href="https://feedeo.com.br" className="text-[#c084fc] hover:underline">
                https://feedeo.com.br
              </a>
            </p>
          </section>
        </div>

        <p className="mt-8 text-center text-[12px] text-white/30">
          <Link href="/" className="hover:text-white/50 hover:underline">
            Voltar para o início
          </Link>
        </p>
      </article>
    </div>
  );
}
