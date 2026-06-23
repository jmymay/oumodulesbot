#include <boost/algorithm/string/replace.hpp>
#include <google/cloud/functions/framework.h>
#include <google/cloud/functions/http_request.h>
#include <google/cloud/functions/http_response.h>
#include <nlohmann/json.hpp>

#include <string>

#include "interaction_lib.h"
#include "verify_ed25519.h"

namespace gcf = ::google::cloud::functions;
namespace oubot = ::ou_modules_bot_interaction;

using ou_modules_bot::HexDecode;
using ou_modules_bot::VerifyEd25519;

constexpr auto public_key = HexDecode<64>(
    "36796b869d4a48ef7c75744b005ebac9a28b6ffebf842d91c370663cd11e7c87");

bool VerifyEd25519FromRequest(const gcf::HttpRequest &request) {
  auto const &headers = request.headers();
  auto ts = headers.find("x-signature-timestamp");

  auto signature = headers.find("x-signature-ed25519");
  if (ts == headers.end() || signature == headers.end() ||
      signature->second.size() != 128) {
    return false;
  }
  std::string message = ts->second + request.payload();
  return VerifyEd25519(public_key.data(), signature->second.c_str(),
                       message.c_str(), message.size());
}

gcf::HttpResponse interactions(const gcf::HttpRequest request) {

  if (!VerifyEd25519FromRequest(request))
    return gcf::HttpResponse{}
        .set_payload("invalid request signature")
        .set_result(401);

  std::string result;
  auto request_json = nlohmann::json::parse(request.payload(), /*cb=*/nullptr,
                                            /*allow_exceptions=*/false);
  int type = request_json["type"];
  if (type == 1) // ping
  {
    result = "{\"type\": 1}";
  } else if (type != 2) // application command
  {
    return gcf::HttpResponse{}.set_result(404);
  } else {
    oubot::Handler handler(request_json);
    result = handler.Handle();
  }

  return gcf::HttpResponse{}
      .set_header("Content-Type", "application/json")
      .set_payload(result);
}

int main(int argc, char* argv[]) {
  return gcf::Run(argc, argv, gcf::MakeFunction(interactions));
}
