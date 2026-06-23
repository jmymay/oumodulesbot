#ifndef OUMODULES_BOT_INTERACTION_LIB_H
#define OUMODULES_BOT_INTERACTION_LIB_H


#include <nlohmann/json.hpp>

namespace ou_modules_bot_interaction {

class Handler {
public:
    Handler(::nlohmann::json::const_reference request_json);
    ~Handler();

    std::string Handle();

private:
    class Impl;
    std::unique_ptr<Impl> impl_;
};


} // namespace ou_modules_bot_interaction

#endif // OUMODULES_BOT_INTERACTION_LIB_H
